"""Download one Sentinel-2 L2A stack per fire-date, clipped to the fire's AOI.

Reads `registry/aoi.gpkg` (bbox + scouted dates) joined to `registry/fires_master.csv`
(fire_id), queries Element 84 Earth Search, and writes

    data/fires/<fire_id>/<YYYY-MM-DD>_<role>.tif      role in pre | during | final, 20 m

(the folder carries the fire_id; it is also stored in each file's FIRE_ID tag).
10 bands, uint16, nodata 0:  1 B12 · 2 B11 · 3 B8A · 4 B04 · 5 SCL · 6 B02 · 7 B03 · 8 B05 · 9 B06 · 10 B07
(10 m bands B02/B03/B04 -> 20 m average). Bands 1-5 keep their original positions so the QGIS styles and
make_indices.py work unchanged; 6-10 complete the 9 spectral bands used by the FLOGA-trained models.
Styled views on this one file: swir = bands 1/3/4 (B12/B8A/B04), atm-pen = bands 1/2/3
(B12/B11/B8A), both fixed 0-4000. Every date of a fire lands on the
same 20 m grid in the fire's UTM zone, snapped to the native Sentinel-2 pixel edges, so dates
align with zero resampling. AOIs spanning several MGRS tiles are mosaicked; tiles from a
minority UTM zone are reprojected into the majority zone.

Pixel values are stored as delivered. Whether they still carry the processing-baseline
>= 04.00 BOA offset (+1000 DN) is detected from the pixels themselves (STAC metadata alone is
not reliable on Earth Search) and recorded per band as the tag BOA_ADD_OFFSET (0 or -1000);
make_indices.py uses it to convert to reflectance. One appended row per written file goes to
registry/scenes.csv.

Usage:
    python scripts/download_scenes.py --dry-run                 # validate + plan every fire
    python scripts/download_scenes.py --fire 1920-03
    python scripts/download_scenes.py --fire 1920-01,1920-02 [--overwrite]
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import rasterio
from affine import Affine
from pystac_client import Client
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds
from shapely.geometry import box, shape

import _registry
from _registry import ROOT, SCENES_CSV, Fire, select_fires

EARTH_SEARCH = "https://earth-search.aws.element84.com/v1"
# Fallback when Earth Search has no scene for a date (e.g. its archive has nothing over
# Australia before 2016). Free and anonymous; assets need a short-lived SAS token.
PLANETARY_COMPUTER = "https://planetarycomputer.microsoft.com/api/stac/v1"
PC_COLLECTION = "sentinel-2-l2a"
PC_TOKEN_URL = f"https://planetarycomputer.microsoft.com/api/sas/v1/token/{PC_COLLECTION}"
RES = 20
# (band name, native resolution); asset keys differ per source
BANDS = [("B12", 20), ("B11", 20), ("B8A", 20), ("B04", 10), ("SCL", 20),
         ("B02", 10), ("B03", 10), ("B05", 20), ("B06", 20), ("B07", 20)]
ASSET_KEYS = {"earth-search": {"B12": "swir22", "B11": "swir16", "B8A": "nir08", "B04": "red", "SCL": "scl",
                               "B02": "blue", "B03": "green", "B05": "rededge1", "B06": "rededge2",
                               "B07": "rededge3"},
              "planetary-computer": {b: b for b, _ in BANDS}}
SOURCE = {}                          # item.id -> source name, filled by find_items
SCL_CLOUD = (3, 8, 9, 10)           # cloud shadow, cloud medium/high, cirrus
BOA_OFFSET_DN = -1000

GDAL_ENV = dict(
    GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
    CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
    GDAL_HTTP_MULTIRANGE="YES",
    GDAL_HTTP_MERGE_CONSECUTIVE_RANGES="YES",
    GDAL_HTTP_MAX_RETRY="5",
    GDAL_HTTP_RETRY_DELAY="2",
    VSI_CACHE="TRUE",
)

SCENES_COLUMNS = ["fire_id", "date", "scene_id", "tile", "cloud_cover_tile", "scl_cloud_pct_aoi",
                  "boa_offset_applied", "file", "downloaded_at", "role", "usable", "notes"]



def _rel(path: Path) -> str:
    """Path relative to the repo when inside it, otherwise absolute (e.g. with --out-dir)."""
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()

# --- grid ------------------------------------------------------------------------------

def utm_epsg(zone: int, south: bool) -> int:
    return (32700 if south else 32600) + zone


def target_grid(geom):
    """UTM zone holding most of the AOI, and the AOI's bounds in it snapped outward to 20 m."""
    minx, miny, maxx, maxy = geom.bounds
    south = (miny + maxy) / 2 < 0
    zones = range(int((minx + 180) // 6) + 1, int((maxx + 180) // 6) + 2)
    share = {z: geom.intersection(box(-180 + 6 * (z - 1), -90, -180 + 6 * z, 90)).area for z in zones}
    zone = max(share, key=share.get)
    epsg = utm_epsg(zone, south)

    x0, y0, x1, y1 = transform_bounds("EPSG:4326", f"EPSG:{epsg}", *geom.bounds, densify_pts=21)
    x0, y0 = math.floor(x0 / RES) * RES, math.floor(y0 / RES) * RES
    x1, y1 = math.ceil(x1 / RES) * RES, math.ceil(y1 / RES) * RES
    width, height = int((x1 - x0) / RES), int((y1 - y0) / RES)
    return epsg, Affine(RES, 0, x0, 0, -RES, y1), width, height, sorted(z for z, a in share.items() if a > 0)


# --- STAC ------------------------------------------------------------------------------

def _baseline(item) -> float:
    try:
        return float(item.properties.get("s2:processing_baseline", 0))
    except (TypeError, ValueError):
        return 0.0


def _tile(item) -> str:
    p = item.properties
    return p.get("grid:code", "").replace("MGRS-", "") or p.get("s2:mgrs_tile") or item.id.split("_")[1]


_pc_token = {"token": None, "expiry": datetime.min.replace(tzinfo=timezone.utc)}


def _pc_sas_token() -> str:
    """Anonymous Planetary Computer SAS token, refreshed when under 10 minutes remain."""
    if _pc_token["expiry"] - datetime.now(timezone.utc) < timedelta(minutes=10):
        with urllib.request.urlopen(PC_TOKEN_URL, timeout=30) as r:
            tok = json.load(r)
        _pc_token["token"] = tok["token"]
        _pc_token["expiry"] = datetime.fromisoformat(tok["msft:expiry"].replace("Z", "+00:00"))
    return _pc_token["token"]


def href(item, band: str) -> str:
    """Readable URL of one band of an item, whichever source it came from."""
    source = SOURCE.get(item.id, "earth-search")
    url = item.assets[ASSET_KEYS[source][band]].href
    return f"{url}?{_pc_sas_token()}" if source == "planetary-computer" else url


def _epsg(item) -> int:
    code = item.properties.get("proj:code") or f"EPSG:{item.properties.get('proj:epsg')}"
    return int(str(code).split(":")[-1])


def find_items(cat, geom, d: date, collection: str, epsg: int, source: str = "earth-search"):
    """
    The tiles needed to cover the AOI on date d, in fill order.

    Duplicate products of one tile (`_0`/`_1`) are the same acquisition processed twice: keep the
    newest processing baseline (least cloud as tie-break). Tiles in the target UTM zone come first,
    so reprojected minority-zone tiles only fill what the target zone can't; any tile that adds no
    uncovered AOI area is dropped (MGRS overlap often means one tile covers everything).
    """
    items = [i for i in cat.search(collections=[collection], bbox=geom.bounds,
                                   datetime=f"{d.isoformat()}/{d.isoformat()}", max_items=200).items()
             if shape(i.geometry).intersects(geom)]
    best = {}
    for it in items:
        t = _tile(it)
        key = (_baseline(it), -it.properties.get("eo:cloud_cover", 100))
        if t not in best or key > best[t][0]:
            best[t] = (key, it)
    ordered = sorted((it for _, it in best.values()),
                     key=lambda i: (_epsg(i) != epsg, -shape(i.geometry).intersection(geom).area))
    chosen, covered = [], None
    for it in ordered:
        part = shape(it.geometry).intersection(geom)
        new = part if covered is None else part.difference(covered)
        if new.area > 1e-3 * geom.area:
            chosen.append(it)
            SOURCE[it.id] = source
            covered = part if covered is None else covered.union(part)
    return chosen


def nearby_passes(cat, geom, d: date, collection: str, days: int = 5) -> str:
    items = cat.search(collections=[collection], bbox=geom.bounds,
                       datetime=f"{(d - timedelta(days=days)).isoformat()}/{(d + timedelta(days=days)).isoformat()}",
                       max_items=200).items()
    by_day = {}
    for it in items:
        by_day.setdefault(it.datetime.date(), []).append(it.properties.get("eo:cloud_cover", 100))
    return ", ".join(f"{k} ({min(v):.0f}% tile cloud)" for k, v in sorted(by_day.items())) or "none"


# --- BOA offset ------------------------------------------------------------------------

def _aoi_window(src, geom):
    l, b, r, t = transform_bounds("EPSG:4326", src.crs, *geom.bounds, densify_pts=21)
    win = from_bounds(l, b, r, t, src.transform).round_offsets().round_lengths()
    return win.intersection(rasterio.windows.Window(0, 0, src.width, src.height))


def offset_from_metadata(item) -> int:
    """Baseline >= 04.00 carries the offset unless Earth Search says it already removed it."""
    applied = item.properties.get("earthsearch:boa_offset_applied")
    return BOA_OFFSET_DN if _baseline(item) >= 4.0 and applied is not True else 0


def offset_from_pixels(item, geom) -> int | None:
    """
    Red reflectance of vegetation and water is almost always < 0.1. Offset-free data therefore
    has most such pixels below DN 1000; data still carrying +1000 has almost none.
    Returns 0, -1000, or None when there is too little vegetation/water to tell.
    """
    try:
        with rasterio.open(href(item, "SCL")) as s:
            w = _aoi_window(s, geom)
            f = max(1, int(max(w.width, w.height) // 1024))
            shp = (max(1, int(w.height // f)), max(1, int(w.width // f)))
            scl = s.read(1, window=w, out_shape=shp, resampling=Resampling.nearest)
        with rasterio.open(href(item, "B04")) as s:
            red = s.read(1, window=_aoi_window(s, geom), out_shape=shp, resampling=Resampling.nearest)
    except Exception as e:                                   # network hiccup -> fall back to metadata
        print(f"      offset check failed for {item.id}: {e}")
        return None
    m = np.isin(scl, (4, 6)) & (red > 0)
    if m.sum() < 500:
        return None
    frac_dark = float((red[m] < 1000).mean())
    if frac_dark > 0.2:
        return 0
    if frac_dark < 0.01:
        return BOA_OFFSET_DN
    return None


def decide_offsets(items, geom):
    """Per-item offset (pixels first, metadata as fallback) plus a log line per item."""
    result, lines = {}, []
    for it in items:
        meta, pix = offset_from_metadata(it), offset_from_pixels(it, geom)
        off = pix if pix is not None else meta
        src = "pixels" if pix is not None else "metadata"
        note = "" if pix is None or pix == meta else f"  (metadata said {meta}; using pixels)"
        result[it.id] = (off, src)
        lines.append(f"      {it.id}: baseline {it.properties.get('s2:processing_baseline')} "
                     f"boa_offset_applied={it.properties.get('earthsearch:boa_offset_applied')} "
                     f"-> offset {off} DN [{src}]{note}")
    return result, lines


# --- download --------------------------------------------------------------------------

def mosaic_band(items, band, native_res, is_scl, epsg, transform, width, height, dn_shift):
    """Warp every tile onto the target grid; earlier tiles (target zone first) win where they overlap."""
    out = np.zeros((height, width), dtype=np.uint16)
    for it in items:
        with rasterio.open(href(it, band)) as src:
            same_zone = src.crs.to_epsg() == epsg
            if is_scl:
                rs = Resampling.nearest
            elif native_res != RES:
                rs = Resampling.average
            else:
                rs = Resampling.nearest if same_zone else Resampling.bilinear
            with WarpedVRT(src, crs=f"EPSG:{epsg}", transform=transform, width=width, height=height,
                           resampling=rs, nodata=0, src_nodata=0) as vrt:
                arr = vrt.read(1).astype(np.int32)
        valid = arr > 0
        if not is_scl and dn_shift[it.id]:
            arr[valid] = np.clip(arr[valid] + dn_shift[it.id], 1, 65535)
        fill = (out == 0) & valid
        out[fill] = arr[fill]
        del arr, valid, fill
    return out


def download_date(fire: Fire, d: date, role: str, items, offsets, grid, overwrite: bool):
    epsg, transform, width, height, _ = grid
    out_path = fire.folder / f"{d.isoformat()}_{role}.tif"
    if out_path.exists() and not overwrite:
        print(f"    exists, skipped: {_rel(out_path)}")
        return

    # One offset per file: if tiles disagree, shift the minority onto the majority's convention.
    offs = [offsets[i.id][0] for i in items]
    target = max(set(offs), key=offs.count)
    # BOA_ADD_OFFSET -1000 means the DN carries +1000, so moving a tile from offset a to b shifts DN by a - b.
    dn_shift = {i.id: offsets[i.id][0] - target for i in items}
    if any(dn_shift.values()):
        print(f"    tiles disagree on BOA offset; shifting {sum(bool(v) for v in dn_shift.values())} "
              f"tile(s) by DN so the whole file uses offset {target}")

    fire.folder.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".tmp.tif")
    profile = dict(driver="GTiff", width=width, height=height, count=len(BANDS), dtype="uint16",
                   crs=f"EPSG:{epsg}", transform=transform, nodata=0, tiled=True,
                   blockxsize=512, blockysize=512, compress="deflate", predictor=2,
                   BIGTIFF="IF_SAFER")
    cloud_pct = float("nan")
    with rasterio.open(tmp, "w", **profile) as dst:
        for bi, (name, native) in enumerate(BANDS, start=1):
            arr = mosaic_band(items, name, native, name == "SCL", epsg, transform, width, height, dn_shift)
            dst.write(arr, bi)
            dst.set_band_description(bi, name)
            if name == "SCL":
                valid = arr > 0
                cloud_pct = 100 * float(np.isin(arr[valid], SCL_CLOUD).mean()) if valid.any() else float("nan")
                dst.update_tags(bi, BOA_ADD_OFFSET="n/a")
            else:
                dst.update_tags(bi, BOA_ADD_OFFSET=str(target), SCALE="0.0001")
            print(f"    {name} done ({100 * float((arr > 0).mean()):.0f}% of grid has data)")
            del arr
        sources = sorted({SOURCE.get(i.id, "earth-search") for i in items})
        dst.update_tags(FIRE_ID=fire.fire_id, FIRE_CODE=fire.fire_code, DATE=d.isoformat(), ROLE=role,
                        SOURCE=";".join(sources), SCENE_IDS=";".join(i.id for i in items),
                        PROCESSING_BASELINES=";".join(str(i.properties.get("s2:processing_baseline")) for i in items),
                        BOA_OFFSET_SOURCE=";".join(f"{i.id}:{offsets[i.id][1]}" for i in items),
                        REFLECTANCE="(DN + BOA_ADD_OFFSET) * 0.0001")
        dst.build_overviews([f for f in (2, 4, 8, 16, 32) if max(width, height) / f >= 256] or [2],
                            Resampling.nearest)
    os.replace(tmp, out_path)
    print(f"    wrote {_rel(out_path)}  (AOI cloud/shadow per SCL: {cloud_pct:.1f}%)")

    append_scene_row(dict(
        fire_id=fire.fire_id, date=d.isoformat(), scene_id=";".join(i.id for i in items),
        tile=";".join(_tile(i) for i in items),
        cloud_cover_tile=";".join(f"{i.properties.get('eo:cloud_cover', float('nan')):.1f}" for i in items),
        scl_cloud_pct_aoi=f"{cloud_pct:.1f}",
        boa_offset_applied=";".join(str(i.properties.get("earthsearch:boa_offset_applied")) for i in items),
        file=_rel(out_path),
        downloaded_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        role=role, usable="",
        notes="" if sources == ["earth-search"] else f"source: {';'.join(sources)}"))


def append_scene_row(row: dict):
    """Append only; the existing header (and any human-edited columns) is never rewritten."""
    new_file = not SCENES_CSV.exists() or SCENES_CSV.stat().st_size == 0
    if not new_file:
        with open(SCENES_CSV, newline="", encoding="utf-8") as fh:
            header = next(csv.reader(fh))
        with open(SCENES_CSV, "rb") as fh:                      # make sure we start on a new line
            fh.seek(-1, os.SEEK_END)
            needs_newline = fh.read(1) not in (b"\n", b"\r")
    else:
        header, needs_newline = SCENES_COLUMNS, False
    with open(SCENES_CSV, "a", newline="", encoding="utf-8") as fh:
        if needs_newline:
            fh.write("\r\n")
        w = csv.DictWriter(fh, fieldnames=header, extrasaction="ignore")
        if new_file:
            w.writeheader()
        w.writerow(row)


# --- main ------------------------------------------------------------------------------

def process_fire(cat, pc_cat, fire: Fire, collection: str, dry_run: bool, overwrite: bool):
    grid = target_grid(fire.geometry)
    epsg, _, width, height, zones = grid
    km = (width * RES / 1000, height * RES / 1000)
    print(f"\n{fire.fire_code} -> {fire.fire_id}")
    print(f"  AOI {km[0]:.0f} x {km[1]:.0f} km | grid {width} x {height} px @ 20 m | "
          f"EPSG:{epsg} | ~{width * height * 2 * len(BANDS) / 1e6:.0f} MB/date uncompressed")
    if len(zones) > 1:
        print(f"  AOI spans UTM zones {zones}: grid in zone {epsg % 100}; a tile from another zone is only "
              f"used (and reprojected) where zone-{epsg % 100} tiles don't cover the AOI")
    for w in fire.warnings:
        print(f"  WARNING: {w}")

    for d, role in fire.dates:
        items, source = find_items(cat, fire.geometry, d, collection, epsg), "Earth Search"
        if not items:
            items = find_items(pc_cat(), fire.geometry, d, PC_COLLECTION, epsg, "planetary-computer")
            source = "Planetary Computer (not on Earth Search)"
        if not items:
            nearby = nearby_passes(cat, fire.geometry, d, collection)
            if nearby == "none":
                nearby = nearby_passes(pc_cat(), fire.geometry, d, PC_COLLECTION) + " [Planetary Computer]"
            print(f"  {d} {role}: NO Sentinel-2 pass over the AOI in Earth Search or Planetary Computer. "
                  f"Nearby: {nearby}")
            continue
        tiles = ", ".join(f"{_tile(i)} ({i.properties.get('eo:cloud_cover', 0):.0f}% tile cloud, "
                          f"baseline {i.properties.get('s2:processing_baseline')}"
                          f"{', REPROJECTED from zone ' + str(_epsg(i) % 100) if _epsg(i) != epsg else ''})"
                          for i in items)
        print(f"  {d} {role}: {len(items)} tile(s) from {source}: {tiles}")
        if dry_run:
            continue
        offsets, lines = decide_offsets(items, fire.geometry)
        print("\n".join(lines))
        download_date(fire, d, role, items, offsets, grid, overwrite)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fire", help="one or more fire_codes, comma-separated, e.g. 1920-03 or "
                                   "1920-01,1920-02,1920-05 (omit for every fire)")
    ap.add_argument("--dry-run", action="store_true", help="validate and print the plan; download nothing")
    ap.add_argument("--overwrite", action="store_true", help="re-download dates whose file already exists")
    ap.add_argument("--collection", default="sentinel-2-l2a", help="Earth Search collection")
    ap.add_argument("--out-dir", help="write <out-dir>/<fire_id>/... instead of data/fires/<fire_id>/...")
    args = ap.parse_args()

    if args.out_dir:
        _registry.FIRES_DIR = Path(args.out_dir).resolve()
    fires = select_fires(args.fire)
    print(f"{len(fires)} fire(s) to process{' (dry run)' if args.dry_run else ''}")
    cat = Client.open(EARTH_SEARCH)
    pc = {}

    def pc_cat():                                    # opened only if a date needs the fallback
        if "cat" not in pc:
            pc["cat"] = Client.open(PLANETARY_COMPUTER)
        return pc["cat"]

    with rasterio.Env(**GDAL_ENV):
        for fire in fires:
            try:
                process_fire(cat, pc_cat, fire, args.collection, args.dry_run, args.overwrite)
            except Exception as e:                               # one bad fire must not stop a batch
                print(f"  FAILED {fire.fire_code}: {type(e).__name__}: {e}")
                if args.fire:
                    raise


if __name__ == "__main__":
    main()
