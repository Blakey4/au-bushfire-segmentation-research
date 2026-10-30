"""Write the protocol 5.2 view styles as QGIS .qml files into styles/ (fixed stretches).

Run with QGIS python; any stack / nbr / dnbr tif serves as a template (styles are not tied to a file):
    python-qgis-ltr.bat scripts/make_styles.py styles <date>_final.tif <date>_nbr.tif dnbr.tif
"""
import sys, os
from qgis.core import (Qgis, QgsApplication, QgsRasterLayer, QgsMultiBandColorRenderer, QgsContrastEnhancement,
                       QgsSingleBandGrayRenderer, QgsSingleBandPseudoColorRenderer, QgsRasterShader,
                       QgsColorRampShader, QgsStyle, QgsRasterMinMaxOrigin)
from qgis.PyQt.QtGui import QColor
app = QgsApplication([], False); app.initQgis()
OUT = sys.argv[1]; STACK, NBR, DNBR = sys.argv[2:5]

def ce(prov, band, lo, hi):
    c = QgsContrastEnhancement(prov.dataType(band))
    c.setContrastEnhancementAlgorithm(QgsContrastEnhancement.StretchToMinimumMaximum)
    c.setMinimumValue(lo); c.setMaximumValue(hi); return c

def fixed(r):
    o = r.minMaxOrigin(); o.setLimits(Qgis.RasterRangeLimit.NotSet); r.setMinMaxOrigin(o)

def save(lay, name):
    p = os.path.join(OUT, name + '.qml'); msg, ok = lay.saveNamedStyle(p); print(name, ok, msg)

st = QgsRasterLayer(STACK, 'stack'); pv = st.dataProvider()
# stack bands: 1 B12, 2 B11, 3 B8A, 4 B04, 5 SCL, 6 B02, 7 B03, 8 B05, 9 B06, 10 B07; (lo, hi) per channel
for name, bands, lims in [('atm-pen', (1, 2, 3), [(0, 4000)] * 3), ('swir', (1, 3, 4), [(0, 4000)] * 3),
                          ('agriculture', (2, 3, 6), [(0, 5000), (0, 4500), (0, 1500)]),     # B11/B8A/B02 (B8A for B8)
                          ('false-colour-ir', (3, 4, 7), [(0, 4500), (0, 2500), (0, 2000)])]:  # B8A/B04/B03
    r = QgsMultiBandColorRenderer(pv, *bands)
    r.setRedContrastEnhancement(ce(pv, bands[0], *lims[0])); r.setGreenContrastEnhancement(ce(pv, bands[1], *lims[1]))
    r.setBlueContrastEnhancement(ce(pv, bands[2], *lims[2])); fixed(r)
    st.setRenderer(r); st.resampleFilter().setZoomedOutResampler(None); save(st, name)

nb = QgsRasterLayer(NBR, 'nbr'); pn = nb.dataProvider()
for name, lo, hi in [('nbr', -0.5, 0.7), ('nbr2', -0.1, 0.4)]:
    r = QgsSingleBandGrayRenderer(pn, 1); r.setContrastEnhancement(ce(pn, 1, lo, hi)); fixed(r)
    nb.setRenderer(r); save(nb, name)

dn = QgsRasterLayer(DNBR, 'dnbr'); pd_ = dn.dataProvider()
ramp = QgsStyle.defaultStyle().colorRamp('Inferno')
# same ramp for all change/burn indices; rbr and bais2 styles only need a float single-band template
for name, lo, hi in [('dnbr', -0.1, 0.8), ('rbr', -0.1, 0.6), ('bais2', 0.2, 1.2)]:
    n = 11
    items = [QgsColorRampShader.ColorRampItem(lo + (hi - lo) * i / (n - 1), ramp.color(i / (n - 1)),
                                              f'{lo + (hi - lo) * i / (n - 1):.2f}') for i in range(n)]
    crs = QgsColorRampShader(lo, hi); crs.setColorRampType(QgsColorRampShader.Interpolated)
    crs.setSourceColorRamp(ramp.clone()); crs.setColorRampItemList(items); crs.setClip(False)
    sh = QgsRasterShader(); sh.setRasterShaderFunction(crs)
    r = QgsSingleBandPseudoColorRenderer(pd_, 1, sh); r.setClassificationMin(lo); r.setClassificationMax(hi); fixed(r)
    dn.setRenderer(r); save(dn, name)
app.exitQgis()
