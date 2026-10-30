"""Compute the derived annotation views for each fire from its downloaded stacks.

Reads `registry/scenes.csv` (written by download_scenes.py) and writes, flat into
`data/fires/<fire_id>/`:

    <date>_nbr.tif            (B8A-B12)/(B8A+B12)   every downloaded date     float32
    <date>_nbr2.tif           (B11-B12)/(B11+B12)   every downloaded date     float32
    dnbr.tif                  NBR(pre) - NBR(final)  needs pre + final         float32
    swir-highlight.tif        final-date swir    composite (R=B12 G=B8A B=B04) \\  fixed 0-0.4 reflectance
    atm-pen-highlight.tif     final-date atm-pen composite (R=B12 G=B11 B=B8A) /  stretch, brightness
                              scaled by dNBR: unchanged ground dimmed, burnt ground at full colour.
                              uint8 RGB, displays in QGIS without a style.
    dnbr_seed.gpkg            (--seeds) thresholded dNBR polygons, method='dnbr_seed'

The folder carries the fire_id (also stored in each file's FIRE_ID tag). `swir` and `atm-pen`
themselves are QGIS styles on the downloaded stack, not files.

Pixel values are converted to reflectance with each band's BOA_ADD_OFFSET tag (written by
download_scenes.py), so scenes with and without the baseline-04.00 offset mix correctly.
Existing outputs are skipped unless --overwrite.

Usage:
    python scripts/make_indices.py --fire 1920-03
    python scripts/make_indices.py --fire 1920-01,1920-02 --seeds [--seed-threshold 0.2]
"""
from __future__ import annotations

import argparse

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.enums import Resampling
from rasterio.features import shapes, sieve
from shapely.geometry import shape

from _registry import ROOT, SCENES_CSV, Fire, select_fires

SWIR_MAX_REFL = 0.4              # same as the styles' fixed 0-4000 DN stretch on offset-free data
# highlight file -> the composite it brightens (R, G, B)
HIGHLIGHTS = {"swir-highlight": ("B12", "B8A", "B04"),
              "atm-pen-highlight": ("B12", "B11", "B8A")}
MIN_SEED_AREA_M2 = 20_000        # 2 ha, as in dnbr_seed.py
SEED_SIMPLIFY_M = 20
SEED_EXCLUDE_SCL = (3, 6, 8, 9, 10)   # cloud shadow, water, cloud medium/high, cirrus


# --- io -------------------------------------------------------------------------------

def read_reflectance(path):
    """{band name: float32 reflectance, NaN where no data} plus the source profile."""
    with rasterio.open(path) as src:
        names = list(src.descriptions)
        out = {}
        for i, name in enumerate(names, start=1):
            if name == "SCL":
                continue
            dn = src.read(i).astype(np.float32)
            tag = src.tags(i).get("BOA_ADD_OFFSET")
            if tag is None:
                print(f"    WARNING: {path.name} band {name} has no BOA_ADD_OFFSET tag; assuming 0")
            offset = float(tag) if tag not in (None, "n/a") else 0.0
            refl = (dn + offset) / 10000.0
            refl[dn == 0] = np.nan
            out[name] = np.clip(refl, 0, None, where=~np.isnan(refl), out=refl)
        return out, src.profile.copy()


def read_scl(path):
    with rasterio.open(path) as src:
        return src.read(list(src.descriptions).index("SCL") + 1)


def _grid(profile):
    return profile["crs"], profile["transform"], profile["width"], profile["height"]


def _overview_factors(profile):
    return [f for f in (2, 4, 8, 16, 32) if max(profile["width"], profile["height"]) / f >= 256] or [2]


def write_float(path, arr, profile, tags):
    p = dict(driver="GTiff", width=profile["width"], height=profile["height"], count=1,
             dtype="float32", crs=profile["crs"], transform=profile["transform"], nodata=np.nan,
             tiled=True, blockxsize=512, blockysize=512, compress="deflate", predictor=3,
             BIGTIFF="IF_SAFER")
    with rasterio.open(path, "w", **p) as dst:
        dst.write(arr.astype(np.float32), 1)
        dst.set_band_description(1, tags["VIEW"])
        dst.update_tags(**tags)
        dst.build_overviews(_overview_factors(profile), Resampling.average)
    print(f"    wrote {path.relative_to(ROOT)}")


def write_rgb(path, rgb, profile, bands, tags):
    p = dict(driver="GTiff", width=profile["width"], height=profile["height"], count=3,
             dtype="uint8", crs=profile["crs"], transform=profile["transform"], nodata=0,
             photometric="RGB", tiled=True, blockxsize=512, blockysize=512, compress="deflate",
             BIGTIFF="IF_SAFER")
    with rasterio.open(path, "w", **p) as dst:
        dst.write(rgb)
        for i, (c, b) in enumerate(zip(("red", "green", "blue"), bands), start=1):
            dst.set_band_description(i, f"{c}: {b}")
        dst.update_tags(**tags)
        dst.build_overviews(_overview_factors(profile), Resampling.average)
    print(f"    wrote {path.relative_to(ROOT)}")


# --- views ----------------------------------------------------------------------------

def norm_diff(a, b):
    with np.errstate(divide="ignore", invalid="ignore"):
        return (a - b) / (a + b)


def highlight(final_refl, bands, dnbr, floor, sat):
    """Final-date composite colours; brightness floor..1 as dNBR goes 0..sat (unknown dNBR -> floor)."""
    rgb = np.stack([final_refl[b] for b in bands])
    valid = ~np.isnan(rgb).any(axis=0)
    rgb = np.clip(np.nan_to_num(rgb) / SWIR_MAX_REFL, 0, 1)
    w = floor + (1 - floor) * np.clip(np.nan_to_num(dnbr, nan=0.0) / sat, 0, 1)
    out = np.round(rgb * w * 255).astype(np.uint8)
    out[:, valid] = np.maximum(out[:, valid], 1)          # keep 0 for nodata only
    out[:, ~valid] = 0
    return out


def dnbr_seeds(dnbr, profile, threshold, fire_id, final_date, exclude=None):
    """`exclude`: pixels never seeded (water / cloud / shadow per SCL), where NBR is meaningless."""
    mask = (np.nan_to_num(dnbr, nan=-1) > threshold)
    if exclude is not None:
        mask &= ~exclude
    mask = mask.astype(np.uint8)
    # Remove specks (and fill pinholes) smaller than the minimum seed area on the raster first:
    # on a big fire the raw mask has hundreds of thousands of fragments, and polygonising and
    # dissolving them all is far slower than sieving pixels.
    px_area = abs(profile["transform"].a * profile["transform"].e)
    mask = sieve(mask, size=max(1, int(MIN_SEED_AREA_M2 / px_area)), connectivity=8)
    geoms = [shape(g) for g, v in shapes(mask, mask=mask.astype(bool), connectivity=8,
                                          transform=profile["transform"]) if v == 1]
    if not geoms:
        return None
    gdf = gpd.GeoDataFrame(geometry=geoms, crs=profile["crs"])
    gdf = gdf[gdf.area >= MIN_SEED_AREA_M2]
    if gdf.empty:
        return None
    # Each shape is already one connected region, so no dissolve is needed; simplifying can leave
    # a few invalid rings, which make_valid repairs.
    gdf["geometry"] = gdf.simplify(SEED_SIMPLIFY_M).make_valid()
    gdf = gdf.explode(index_parts=False).reset_index(drop=True)
    gdf = gdf[gdf.geom_type == "Polygon"]
    gdf["fire"] = fire_id
    gdf["date"] = final_date
    gdf["class"] = "burnt"
    gdf["confidence"] = "medium"
    gdf["method"] = "dnbr_seed"
    gdf["notes"] = f"dNBR > {threshold}"
    return gdf


# --- per fire -------------------------------------------------------------------------

def downloaded_scenes(fire: Fire, scenes: pd.DataFrame) -> dict[str, dict]:
    """{date: {'role', 'path'}} for this fire; the latest scenes.csv row per date wins."""
    rows = scenes[scenes["fire_id"] == fire.fire_id]
    out = {}
    for _, r in rows.iterrows():
        path = ROOT / str(r["file"])
        if path.exists():
            out[str(r["date"])] = dict(role=str(r["role"]), path=path)
    return out


def process_fire(fire: Fire, scenes: pd.DataFrame, args):
    print(f"\n{fire.fire_code} -> {fire.fire_id}")
    have = downloaded_scenes(fire, scenes)
    if not have:
        print("  no downloaded scenes in scenes.csv: run download_scenes.py first")
        return
    folder = fire.folder

    def todo(path):
        if path.exists() and not args.overwrite:
            print(f"    exists, skipped: {path.relative_to(ROOT)}")
            return False
        return True

    def tags(view, **extra):
        return dict(FIRE_ID=fire.fire_id, FIRE_CODE=fire.fire_code, VIEW=view, **extra)

    # per-date views
    for d, info in sorted(have.items()):
        nbr_p = folder / f"{d}_nbr.tif"
        nbr2_p = folder / f"{d}_nbr2.tif"
        if not (todo(nbr_p) | todo(nbr2_p)):
            continue
        refl, prof = read_reflectance(info["path"])
        print(f"  {d} ({info['role']})")
        if not nbr_p.exists() or args.overwrite:
            write_float(nbr_p, norm_diff(refl["B8A"], refl["B12"]), prof,
                        tags("nbr", DATE=d, FORMULA="(B8A-B12)/(B8A+B12)"))
        if not nbr2_p.exists() or args.overwrite:
            write_float(nbr2_p, norm_diff(refl["B11"], refl["B12"]), prof,
                        tags("nbr2", DATE=d, FORMULA="(B11-B12)/(B11+B12)"))
        del refl

    # fire-level change views: the registry's current pre and final dates
    pre_d = next((d.isoformat() for d, r in fire.dates if r == "pre"), None)
    fin_d = next((d.isoformat() for d, r in fire.dates if r == "final"), None)
    if not (pre_d in have and fin_d in have):
        missing = [n for n, d in (("pre", pre_d), ("final", fin_d)) if d not in have]
        print(f"  dnbr / highlights skipped: no downloaded {' or '.join(missing)} scene "
              f"(registry pre={pre_d}, final={fin_d})")
        return

    dnbr_p = folder / "dnbr.tif"
    hl_ps = {name: folder / f"{name}.tif" for name in HIGHLIGHTS}
    seed_p = folder / "dnbr_seed.gpkg"
    need = [todo(dnbr_p)] + [todo(p) for p in hl_ps.values()] + ([todo(seed_p)] if args.seeds else [])
    if not any(need):
        return

    pre, pre_prof = read_reflectance(have[pre_d]["path"])
    fin, fin_prof = read_reflectance(have[fin_d]["path"])
    if _grid(pre_prof) != _grid(fin_prof):
        raise SystemExit(f"{fire.fire_id}: pre ({pre_d}) and final ({fin_d}) stacks are on different grids. "
                         f"Was the AOI redrawn between downloads? Re-download both with --overwrite.")
    print(f"  change views: pre {pre_d} -> final {fin_d}")
    dnbr = norm_diff(pre["B8A"], pre["B12"]) - norm_diff(fin["B8A"], fin["B12"])
    del pre
    change = dict(PRE_DATE=pre_d, FINAL_DATE=fin_d)
    if not dnbr_p.exists() or args.overwrite:
        write_float(dnbr_p, dnbr, fin_prof, tags("dnbr", FORMULA="NBR(pre) - NBR(final)", **change))
    for name, bands in HIGHLIGHTS.items():
        if not hl_ps[name].exists() or args.overwrite:
            write_rgb(hl_ps[name], highlight(fin, bands, dnbr, args.highlight_floor, args.highlight_sat),
                      fin_prof, bands, tags(name, HIGHLIGHT_FLOOR=str(args.highlight_floor),
                                            HIGHLIGHT_SAT=str(args.highlight_sat), **change))
    if args.seeds and (not seed_p.exists() or args.overwrite):
        # dNBR over water and cloud is noise (sea glint alone can pass 0.27), so seeds skip any pixel
        # SCL calls water, cloud or cloud shadow on either date. The dNBR raster itself stays unmasked.
        exclude = np.zeros(dnbr.shape, dtype=bool)
        for d in (pre_d, fin_d):
            exclude |= np.isin(read_scl(have[d]["path"]), SEED_EXCLUDE_SCL)
        gdf = dnbr_seeds(dnbr, fin_prof, args.seed_threshold, fire.fire_id, fin_d, exclude)
        if gdf is None:
            print(f"    no seed polygons above dNBR {args.seed_threshold}")
        else:
            gdf.to_file(seed_p, layer="seed", driver="GPKG")
            print(f"    wrote {seed_p.relative_to(ROOT)} ({len(gdf)} polygon(s), dNBR > {args.seed_threshold})")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fire", help="one or more fire_codes, comma-separated, e.g. 1920-03 or "
                                   "1920-01,1920-02,1920-05 (omit for every fire)")
    ap.add_argument("--overwrite", action="store_true", help="recompute outputs that already exist")
    ap.add_argument("--seeds", action="store_true", help="also write dNBR seed polygons")
    ap.add_argument("--seed-threshold", type=float, default=0.27,
                    help="dNBR threshold for seeds (0.27 is a starting point; tune per fire)")
    ap.add_argument("--highlight-floor", type=float, default=0.25,
                    help="highlight brightness of unchanged ground (0-1)")
    ap.add_argument("--highlight-sat", type=float, default=0.44,
                    help="dNBR at which the highlights reach full brightness")
    args = ap.parse_args()

    fires = select_fires(args.fire)
    if not SCENES_CSV.exists():
        raise SystemExit("registry/scenes.csv not found: run download_scenes.py first")
    scenes = pd.read_csv(SCENES_CSV, dtype=str, keep_default_na=False)
    for fire in fires:
        try:
            process_fire(fire, scenes, args)
        except Exception as e:                                   # one bad fire must not stop a batch
            print(f"  FAILED {fire.fire_code}: {type(e).__name__}: {e}")
            if args.fire:
                raise


if __name__ == "__main__":
    main()
