"""Build qgis/zeroshot_labels.qgz for choosing HBB labels (zero-shot plan, step O1).

Loads data/annotations/hbb_selection.gpkg (candidates styled by role, dropdown editors) and every
fire's final + pre stack in atm-pen, with a spatial bookmark per fire. No dNBR layers on purpose.
Run with QGIS's Python, not the venv:

    "C:/Program Files/QGIS 3.44.13/bin/python-qgis-ltr.bat" scripts/make_zeroshot_project.py
"""
import sys
from pathlib import Path

from osgeo import gdal
from qgis.core import (
    Qgis, QgsApplication, QgsBookmark, QgsContrastEnhancement, QgsCoordinateReferenceSystem,
    QgsEditorWidgetSetup, QgsFillSymbol, QgsMultiBandColorRenderer, QgsPalLayerSettings,
    QgsProject, QgsRasterLayer, QgsReferencedRectangle, QgsRuleBasedRenderer, QgsTextFormat,
    QgsVectorLayer, QgsVectorLayerSimpleLabeling,
)
from qgis.PyQt.QtGui import QColor, QFont

ROOT = Path(__file__).resolve().parents[1]
GPKG = ROOT / "data" / "annotations" / "hbb_selection.gpkg"
OUT = ROOT / "qgis" / "zeroshot_labels.qgz"

app = QgsApplication([], False)
app.initQgis()
proj = QgsProject.instance()
proj.setCrs(QgsCoordinateReferenceSystem("EPSG:3577"))
proj.setFilePathStorage(Qgis.FilePathType.Relative)
root = proj.layerTreeRoot()


def fill(color, outline, width="0.5", style="solid", alpha=0):
    c = QColor(color)
    c.setAlpha(alpha)
    return QgsFillSymbol.createSimple({"color": f"{c.red()},{c.green()},{c.blue()},{alpha}",
                                       "outline_color": outline, "outline_width": width,
                                       "outline_style": style})


def value_map(layer, field, values):
    i = layer.fields().indexOf(field)
    layer.setEditorWidgetSetup(i, QgsEditorWidgetSetup("ValueMap", {"map": [{v: v} for v in values]}))


# --- candidates -----------------------------------------------------------------------------
cand = QgsVectorLayer(f"{GPKG}|layername=candidates", "HBB candidates (set role)", "ogr")
assert cand.isValid(), "candidates layer failed to load"
rules = [
    ("role: target", "\"role\" = 'target'", fill("#e31a1c", "#e31a1c", "0.6", alpha=70)),
    ("role: other", "\"role\" = 'other'", fill("#ffd400", "#ffd400", "0.6", alpha=60)),
    ("role: drop", "\"role\" = 'drop'", fill("#999999", "#999999", "0.3", "dot")),
    ("unset, suggested target", "\"role\" IS NULL AND \"suggested\" = 'target'",
     fill("#ff6b6b", "#ff6b6b", "0.6", "dash")),
    ("unset, suggested other", "\"role\" IS NULL AND \"suggested\" = 'other'",
     fill("#fff07a", "#fff07a", "0.6", "dash")),
    ("unset, suggested drop", "\"role\" IS NULL AND \"suggested\" = 'drop'",
     fill("#cccccc", "#cccccc", "0.3", "dash")),
]
rr = QgsRuleBasedRenderer(QgsRuleBasedRenderer.Rule(None))
for label, expr, sym in rules:
    rr.rootRule().appendChild(QgsRuleBasedRenderer.Rule(sym, 0, 0, expr, label))
cand.setRenderer(rr)
value_map(cand, "role", ["target", "other", "drop"])
pal = QgsPalLayerSettings()
pal.fieldName = "\"hbb_name\" || ' | ' || \"agency\" || ' | ' || coalesce(\"latest_date\", '?')"
pal.isExpression = True
fmt = QgsTextFormat()
fmt.setFont(QFont("Arial"))
fmt.setSize(8)
fmt.setColor(QColor("white"))
buf = fmt.buffer()
buf.setEnabled(True)
buf.setColor(QColor("black"))
fmt.setBuffer(buf)
pal.setFormat(fmt)
cand.setLabeling(QgsVectorLayerSimpleLabeling(pal))
cand.setLabelsEnabled(True)
proj.addMapLayer(cand, False)
root.addLayer(cand)

# --- fires ----------------------------------------------------------------------------------
fires = QgsVectorLayer(f"{GPKG}|layername=fires", "fires (fill in per fire)", "ogr")
assert fires.isValid(), "fires layer failed to load"
fires.renderer().setSymbol(fill("#00bfff", "#00bfff", "0.8"))
value_map(fires, "include", ["y", "n"])
value_map(fires, "post_ok", ["y", "n"])
value_map(fires, "label_quality", ["good", "ok", "poor"])
proj.addMapLayer(fires, False)
root.addLayer(fires)

# --- imagery + bookmarks ---------------------------------------------------------------------
img = root.addGroup("imagery (atm-pen: B12/B11/B8A)")
bm = proj.bookmarkManager()
for f in sorted(fires.getFeatures(), key=lambda f: f["fire_code"]):
    code, fid = f["fire_code"], f["fire_id"]
    b = QgsBookmark()
    b.setName(f"{code} {fid[5:]}")
    b.setGroup("zero-shot fires")
    b.setExtent(QgsReferencedRectangle(f.geometry().boundingBox().buffered(1000), fires.crs()))
    bm.addBookmark(b)

    grp = img.addGroup(f"{code} {fid[5:]}")
    grp.setExpanded(False)
    for role, date in (("final", f["final_date"]), ("pre", f["pre_date"])):
        tif = ROOT / "data" / "fires" / fid / f"{date}_{role}.tif"
        if not tif.exists():
            continue
        ds = gdal.Open(str(tif))
        offset = int(float(ds.GetRasterBand(1).GetMetadataItem("BOA_ADD_OFFSET") or 0))
        ds = None
        lo, hi = -offset, 4000 - offset           # same reflectance range whatever the offset
        rl = QgsRasterLayer(str(tif), f"{role} {date}")
        r = QgsMultiBandColorRenderer(rl.dataProvider(), 1, 2, 3)
        for band, setter in ((1, r.setRedContrastEnhancement), (2, r.setGreenContrastEnhancement),
                             (3, r.setBlueContrastEnhancement)):
            ce = QgsContrastEnhancement(rl.dataProvider().dataType(band))
            ce.setContrastEnhancementAlgorithm(QgsContrastEnhancement.StretchToMinimumMaximum)
            ce.setMinimumValue(lo)
            ce.setMaximumValue(hi)
            setter(ce)
        rl.setRenderer(r)
        proj.addMapLayer(rl, False)
        node = grp.addLayer(rl)
        node.setItemVisibilityChecked(role == "final")

OUT.parent.mkdir(exist_ok=True)
ok = proj.write(str(OUT))
print(f"wrote {OUT}: {ok}, {len(bm.bookmarks())} bookmarks")
app.exitQgis()
sys.exit(0 if ok else 1)
