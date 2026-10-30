'''
Supplements each per-season GeoPackage (produced by split_by_season.py from the
static V4 bulk gdb download) with records that exist on the live ArcGIS
FeatureServer behind the Digital Atlas of Australia web viewer but are absent
from the bulk download -- e.g. "Gospers Mountain" and "Currowan 2", two major
2019-20 complexes confirmed missing from the V4 export by direct comparison.

Why both sources, not just the live one
-----------------------------------------
The live service (`Bushfire_Boundaries_Historic_Dec_view`) has FEWER total
features nationally than the V4 bulk file (311,984 vs 345,345 at the time of
writing) -- it is not a superset. The two products have diverged; each has
records the other lacks. So this script is additive only: it never removes or
replaces a local record, it only appends live records that don't already
match one locally (by fire_name + ignition_date + state).

Usage
-----
    python supplement_from_live_service.py                # all files in seasons/
    python supplement_from_live_service.py --season 2019-20
'''

from pathlib import Path
from urllib.parse import quote
import argparse
import subprocess
import sys

import geopandas as gpd
import pandas as pd

GDAL_BIN = Path(r"C:\Program Files\QGIS 3.44.13\bin")
OGR2OGR = GDAL_BIN / "ogr2ogr.exe"

FEATURE_SERVER = ("https://services-ap1.arcgis.com/ypkPEy1AmwPKGNNv/arcgis/rest/services/"
                   "Bushfire_Boundaries_Historic_Dec_view/FeatureServer/0")

SEASONS_DIR = Path(r"D:\au-bushfire-segmentation-research\registry\seasons")

# Columns common to both sources -- live-service extras like OBJECTID /
# Shape__Area / Shape__Length are dropped rather than reconciled with the
# local file's SHAPE_Area / SHAPE_Length naming.
KEEP_COLS = ['fire_id', 'fire_name', 'ignition_date', 'capture_date', 'extinguish_date',
             'fire_type', 'ignition_cause', 'capt_method', 'area_ha', 'perim_km',
             'state', 'agency', 'geometry']


def season_bounds(label):
    y = int(label.split('-')[0])
    return f'{y}-07-01', f'{y + 1}-07-01'


def dedupe_key(df):
    '''fire_name + state only, deliberately ignoring date: the two products
    record ignition_date for the same real fire up to a day or two apart (e.g.
    "Good Good Fire" is 2019-12-28 on the live service, 2019-12-29 locally),
    so an exact-date key lets real duplicates slip through as "new". Both
    sides are already scoped to one season, so a name+state collision between
    two genuinely different fires is an acceptable, rare risk.'''
    return (df['fire_name'].fillna('').str.strip().str.lower() + '|' + df['state'].fillna(''))


def dissolve_live(live):
    '''The live FeatureServer returns one row per polygon PART for a multi-part
    fire sharing the same fire_id, not one row per fire -- observed as e.g. 35
    rows for "Good Good Fire" (fire_id 19122967252), 34 of them area_ha=0.
    Groups by fire_id, unions geometry, and recomputes area_ha from the union
    (the stored area_ha per part undercounts / double-drops slivers).'''
    has_id = live['fire_id'].notna() & (live['fire_id'].astype(str).str.strip() != '')
    grouped, standalone = live[has_id], live[~has_id]

    if not grouped.empty:
        agg = {c: 'first' for c in KEEP_COLS if c not in ('fire_id', 'geometry')}
        agg['ignition_date'] = 'min'
        dissolved = grouped.dissolve(by='fire_id', aggfunc=agg).reset_index()
        utm = dissolved.to_crs(dissolved.estimate_utm_crs())
        dissolved['area_ha'] = utm.geometry.area / 10000
    else:
        dissolved = grouped

    return pd.concat([dissolved, standalone], ignore_index=True)


def fetch_live_season(start, end, tmp_path):
    where = (f"ignition_date >= timestamp '{start} 00:00:00' "
             f"AND ignition_date < timestamp '{end} 00:00:00'")
    url = f"ESRIJSON:{FEATURE_SERVER}/query?where={quote(where)}&outFields=*&f=json"
    if tmp_path.exists():
        tmp_path.unlink()
    proc = subprocess.run([str(OGR2OGR), "--config", "OGR_ORGANIZE_POLYGONS", "SKIP",
                            "-f", "GPKG", str(tmp_path), url,
                            "-nlt", "PROMOTE_TO_MULTI"],
                           capture_output=True, text=True)
    if proc.returncode != 0:
        print(f'  !! live fetch failed: {proc.stderr}', file=sys.stderr)
        return None
    return gpd.read_file(tmp_path)


def supplement_one(season_path, start, end):
    local = gpd.read_file(season_path)
    layer_name = local.columns.name or f'bushfire_boundaries_{season_path.stem.split("_", 2)[-1]}'

    tmp_path = season_path.with_name('_live_tmp.gpkg')
    live = fetch_live_season(start, end, tmp_path)
    tmp_path.unlink(missing_ok=True)
    if live is None or live.empty:
        print('  no live data / fetch failed, left unchanged')
        return

    live = live.to_crs(local.crs)
    live = dissolve_live(live)
    live = live[live['area_ha'].fillna(0) > 0]

    local_keys = set(dedupe_key(local))
    live['_key'] = dedupe_key(live)
    new_rows = live[~live['_key'].isin(local_keys)].drop(columns='_key')

    if new_rows.empty:
        print('  nothing new on the live service for this season')
        return

    new_rows = new_rows[[c for c in KEEP_COLS if c in new_rows.columns]]
    merged = pd.concat([local, new_rows], ignore_index=True)
    merged = gpd.GeoDataFrame(merged, geometry='geometry', crs=local.crs)

    lname = f'bushfire_boundaries_{season_path.stem.split("_", 2)[-1]}'
    merged.to_file(season_path, layer=lname, driver='GPKG')
    added_names = ', '.join(sorted(new_rows['fire_name'].dropna().unique())[:8])
    print(f'  +{len(new_rows)} records added ({len(local)} -> {len(merged)} total)'
          f'{" -- e.g. " + added_names if added_names else ""}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--season', help='Only supplement this one season, e.g. "2019-20".')
    args = parser.parse_args()

    if args.season:
        targets = [SEASONS_DIR / f'bushfire_boundaries_{args.season}.gpkg']
    else:
        targets = sorted(p for p in SEASONS_DIR.glob('bushfire_boundaries_*.gpkg')
                          if 'pre_' not in p.stem and 'unknown_date' not in p.stem)

    for path in targets:
        if not path.exists():
            print(f'{path.name}: not found, skipping')
            continue
        label = path.stem.replace('bushfire_boundaries_', '')
        start, end = season_bounds(label)
        print(f'{label}:')
        supplement_one(path, start, end)
