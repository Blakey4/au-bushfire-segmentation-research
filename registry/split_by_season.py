'''
Splits the national Bushfire Extents Historical gdb into one GeoPackage per
Australian fire season.

Root cause of the QGIS crashes
-------------------------------
It wasn't the file being too big or corrupt. The source is a File Geodatabase
with 324,741 features Australia-wide (1898-2024); some records -- large fire
"complexes" made of many separate burnt patches -- have hundreds of polygon
parts. GDAL's default multipolygon-assembly step (`organizePolygons()`) is
near-quadratic in part count, and on this dataset it made even a single-field,
no-geometry SELECT against the raw gdb hang for minutes. QGIS calls the same
GDAL code path for a "filtered" view (the filter is applied after the read,
not pushed down), which is what was presenting as a crash.

Setting OGR_ORGANIZE_POLYGONS=SKIP avoids that step: a full-table GROUP BY
that previously wouldn't finish in minutes completed in 45s, and a full
324,741-feature copy went from 4m30s to 94s.

Holes: why SKIP alone was wrong, and the repair
-------------------------------------------------
With SKIP, GDAL does not work out which rings are holes, and on this source
every hole ring comes out as a separate, *filled* polygon part stacked on the
fire. In QGIS the hole outlines are visible but filled in. Example, Cudlee
Creek 2019-20: the source has 137 holes (area 22,550 ha = area_ha 22,549);
the SKIP copy had 0 holes and 120 extra parts inside the fire (23,923 ha).
An earlier check against area_ha on the 20 largest fires missed this because
holes are only a few percent of a fire's area.

So after the fast SKIP extraction, `repair_rings()` rebuilds every multi-part
geometry from its rings by nesting depth: a ring inside an even number of
other rings is burnt area, inside an odd number it is a hole (an island in a
hole is burnt again). This is cheap per feature, unlike organizePolygons()
over the whole table, and restores Cudlee Creek exactly.

Design note: per-season extraction, not "convert once then split"
--------------------------------------------------------------------
This machine has only 15.7 GB RAM and, at the time of writing, ~3.4 GB free.
A single-pass full copy of all 324,741 features (even with SKIP, no
-makevalid) was killed twice by Windows for low memory once other work was
running alongside it. Extracting one season directly from the source gdb at a
time keeps peak memory bounded by that season's size -- at most ~16,500
features (2019-20) -- regardless of total system memory pressure, so it's
the safer choice here even though it means the ~780MB source gets opened
~110 times instead of once.

Season counts were read once via a single aggregate SQL query (45s, see
`season_counts.csv` in the same folder as this script) rather than issuing
110 separate per-season COUNT queries.

Season convention
------------------
Matches `fires_master.csv`'s own `season` column: a fire ignited between
1 July of year Y and 30 June of year Y+1 belongs to season "YYYY-YY"
(e.g. a fire on 2019-11-27 -> season "2019-20"). Records with no
ignition_date go to a separate "unknown_date" file rather than being dropped.

Usage
-----
    python split_by_season.py                    # every season, ~110 files
    python split_by_season.py --min-season 2000-01  # bucket everything
                                                     # older into "pre_2000-01"
    python split_by_season.py --season 2019-20    # just one season
'''

from pathlib import Path
import argparse
import csv
import subprocess
import sys

import geopandas as gpd
import pandas as pd
import pyogrio
import shapely
from shapely.geometry import MultiPolygon, Polygon

GDAL_BIN = Path(r"C:\Program Files\QGIS 3.44.13\bin")
OGR2OGR = GDAL_BIN / "ogr2ogr.exe"
OGRINFO = GDAL_BIN / "ogrinfo.exe"

SRC_GDB = Path(r"D:\au-bushfire-segmentation-research\registry\Bushfire Extents - Historical V4 (2025).gdb")
# Two layers, identical schema: the "national" layer excludes NT (that state's
# extents are maintained separately upstream), so both are extracted and
# merged per season rather than using the national layer alone.
SRC_LAYERS = ["National_Historical_Bushfire_Extents_v4", "NT_Historical_Bushfire_Extents_v1"]
OUT_DIR = Path(r"D:\au-bushfire-segmentation-research\registry\seasons")

# Small transaction group size: bounds how much a single ogr2ogr copy holds
# uncommitted in memory at once. Irrelevant at per-season scale (a few
# thousand features) but cheap insurance given how little RAM is free.
TRANSACTION_SIZE = "2000"


def run(cmd, **kw):
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True, **kw)


def season_label(start_year):
    return f'{start_year}-{str(start_year + 1)[-2:]}'


def get_season_counts():
    '''Reads ignition_date attribute-only (no geometry) via pyogrio for each
    source layer and buckets in pandas. Attribute-only reads via pyogrio don't
    hit GDAL's organizePolygons() path at all (unlike an ogrinfo/OGR SQL
    query, which was observed to hang on this larger V4 file even with
    OGR_ORGANIZE_POLYGONS=SKIP set -- the SQL dialect layer seems to still
    materialize geometries internally). Counts from both layers are summed
    per season.'''
    counts, unknown = {}, 0
    for layer in SRC_LAYERS:
        df = pyogrio.read_dataframe(SRC_GDB, layer=layer, read_geometry=False,
                                     columns=['ignition_date'])
        d = pd.to_datetime(df['ignition_date'])
        unknown += int(d.isna().sum())
        season_start = d.dt.year.where(d.dt.month >= 7, d.dt.year - 1).dropna().astype(int)
        for year, n in season_start.value_counts().items():
            counts[year] = counts.get(year, 0) + int(n)

    return counts, unknown


def already_done(out_path, expected):
    '''Lets a killed run be resumed by re-running the same command: skips a
    season whose output file already exists with the expected feature count,
    rather than only being resumable by hand.'''
    if not out_path.exists() or expected is None:
        return False
    info = run([OGRINFO, "-so", "-al", out_path])
    if info.returncode != 0:
        return False  # corrupt/partial from an interrupted write -- redo it
    for line in info.stdout.splitlines():
        if line.strip().startswith('Feature Count:'):
            return int(line.split(':')[1].strip()) == expected
    return False


def fix_rings(geom):
    '''Rebuild one geometry from its rings by nesting depth (see the module
    docstring). Single-part geometries without holes are returned unchanged.'''
    if geom is None or geom.is_empty:
        return geom
    parts = list(geom.geoms) if isinstance(geom, MultiPolygon) else [geom]
    if len(parts) == 1:
        return geom

    rings = [Polygon(p.exterior) for p in parts]
    rings += [Polygon(r) for p in parts for r in p.interiors]
    rings = [r if r.is_valid else shapely.make_valid(r) for r in rings]
    tree = shapely.STRtree(rings)

    depth = []
    for i, ring in enumerate(rings):
        point = ring.representative_point()
        containers = [j for j in tree.query(point, predicate='within')
                      if j != i and rings[j].area > ring.area]
        depth.append(len(containers))

    result = Polygon()
    for d in range(0, max(depth) + 1, 2):
        land = shapely.union_all([r for r, k in zip(rings, depth) if k == d])
        holes = shapely.union_all([r for r, k in zip(rings, depth) if k == d + 1])
        result = result.union(land.difference(holes))
    return MultiPolygon([result]) if isinstance(result, Polygon) else result


def repair_rings(out_path, layer_name):
    '''Apply fix_rings() to every feature of a freshly extracted season file and
    report how many changed, plus the area agreement with area_ha before/after.'''
    gdf = gpd.read_file(out_path, layer=layer_name)
    area_before = gdf.geometry.to_crs(3577).area / 1e4  # GDA94 / Australian Albers (equal area), ha
    gdf['geometry'] = [fix_rings(g) for g in gdf.geometry]
    area_after = gdf.geometry.to_crs(3577).area / 1e4
    changed = int(((area_before - area_after).abs() > 1e-6).sum())

    has_area = gdf['area_ha'] > 0
    ratio_before = (area_before / gdf['area_ha'])[has_area]
    ratio_after = (area_after / gdf['area_ha'])[has_area]
    gdf.to_file(out_path, layer=layer_name, driver='GPKG')
    print(f'  [rings repaired: {changed} features changed; geometry/area_ha within 2%: '
          f'{(abs(ratio_before - 1) < 0.02).mean():.1%} before -> {(abs(ratio_after - 1) < 0.02).mean():.1%} after]',
          end='', flush=True)


def extract(where_clause, out_path, layer_name):
    '''Extracts from both source layers into the same output layer: the first
    write creates the file, the rest append (-update -append).'''
    if out_path.exists():
        out_path.unlink()
    journal = out_path.with_name(out_path.name + '-journal')
    if journal.exists():
        journal.unlink()

    for i, src_layer in enumerate(SRC_LAYERS):
        cmd = [OGR2OGR, "--config", "OGR_ORGANIZE_POLYGONS", "SKIP",
               "-f", "GPKG", out_path, SRC_GDB, src_layer,
               "-nln", layer_name, "-nlt", "PROMOTE_TO_MULTI",
               "-gt", TRANSACTION_SIZE, "-where", where_clause]
        if i > 0:
            cmd += ["-update", "-append"]
        proc = run(cmd)
        if proc.returncode != 0:
            print(f'  !! failed on {src_layer}: {proc.stderr}', file=sys.stderr)
            return None

    repair_rings(out_path, layer_name)

    info = run([OGRINFO, "-so", "-al", out_path])
    for line in info.stdout.splitlines():
        if line.strip().startswith('Feature Count:'):
            return int(line.split(':')[1].strip())
    return None


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--season', help='Only extract this one season, e.g. "2019-20".')
    parser.add_argument('--min-season', default=None,
                        help='Seasons before this one are bucketed into one '
                        '"pre_<season>" file. e.g. --min-season 2000-01')
    args = parser.parse_args()

    if not OGR2OGR.exists():
        sys.exit(f'ogr2ogr not found at {OGR2OGR} -- check the QGIS install path.')

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print('Reading per-season feature counts (one pass, ~45s)...')
    counts, unknown = get_season_counts()
    print(f'{len(counts)} seasons found, {unknown} features with no ignition_date.\n')

    counts_csv = Path(__file__).parent / 'season_counts.csv'
    with open(counts_csv, 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['season', 'n'])
        for y in sorted(counts):
            w.writerow([season_label(y), counts[y]])

    if args.season:
        y = int(args.season.split('-')[0])
        todo, pre = [y], []
    elif args.min_season:
        cutoff = int(args.min_season.split('-')[0])
        todo = sorted(y for y in counts if y >= cutoff)
        pre = sorted(y for y in counts if y < cutoff)
    else:
        todo, pre = sorted(counts), []

    manifest = []
    for y in todo:
        label = season_label(y)
        expected = counts.get(y)
        out_path = OUT_DIR / f'bushfire_boundaries_{label}.gpkg'

        if already_done(out_path, expected):
            print(f'  {label}: {expected:>6} expected -> {out_path.name}  [already done, skipped]')
            manifest.append((label, expected, expected, str(out_path)))
            continue

        where = f"ignition_date >= '{y}-07-01' AND ignition_date < '{y + 1}-07-01'"
        print(f'  {label}: {expected!s:>6} expected -> {out_path.name}', end='', flush=True)
        n = extract(where, out_path, f'bushfire_boundaries_{label}')
        print(f'  [{n} written]' if n is not None else '  [FAILED]')
        manifest.append((label, expected, n, str(out_path)))

    if pre:
        y0 = pre[-1] + 1
        label = f'pre_{season_label(pre[-1])}'
        out_path = OUT_DIR / f'bushfire_boundaries_{label}.gpkg'
        expected = sum(counts.get(y, 0) for y in pre)
        if already_done(out_path, expected):
            print(f'  {label}: {expected:>6} expected -> {out_path.name}  [already done, skipped]')
            manifest.append((label, expected, expected, str(out_path)))
        else:
            where = f"ignition_date < '{y0}-07-01'"
            print(f'  {label}: {expected:>6} expected -> {out_path.name}', end='', flush=True)
            n = extract(where, out_path, f'bushfire_boundaries_{label}')
            print(f'  [{n} written]' if n is not None else '  [FAILED]')
            manifest.append((label, expected, n, str(out_path)))

    if not args.season and unknown:
        out_path = OUT_DIR / 'bushfire_boundaries_unknown_date.gpkg'
        if already_done(out_path, unknown):
            print(f'  unknown_date: {unknown:>6} expected -> {out_path.name}  [already done, skipped]')
            manifest.append(('unknown_date', unknown, unknown, str(out_path)))
        else:
            print(f'  unknown_date: {unknown:>6} expected -> {out_path.name}', end='', flush=True)
            n = extract("ignition_date IS NULL", out_path, 'bushfire_boundaries_unknown_date')
            print(f'  [{n} written]' if n is not None else '  [FAILED]')
            manifest.append(('unknown_date', unknown, n, str(out_path)))

    manifest_path = OUT_DIR / 'manifest.csv'
    with open(manifest_path, 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['season', 'features_expected', 'features_written', 'path'])
        w.writerows(manifest)

    total = sum(n for _, _, n, _ in manifest if n)
    print(f'\n{len(manifest)} files written, {total} features total (see {manifest_path})')
