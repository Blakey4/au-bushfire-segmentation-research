"""Write the HBB label candidates for manual selection in QGIS (zero-shot plan, step C1).

For every fire with downloaded pre + final stacks, every HBB record touching the AOI becomes a
candidate polygon. Ollie sets `role` on each one in QGIS; build_zeroshot.py reads the result.

  - records are clipped to the AOI; records of one agency with the same name and ignition date
    are dissolved into one candidate (agencies split fires into many records)
  - candidates overlapping >= 50% of the smaller one share a `group` (versions of one burn, or a
    part of a bigger record)
  - `suggested` is a metadata-only starting point -- the imagery is never used, so the selection
    isn't biased towards what dNBR or a model sees:
      drop   records that ended before the pre date or started after the final
      within each group: the version with the latest date on record (max of ignition / capture /
      extinguish; ties -> larger) is kept, other versions dropped unless mostly outside it
      target the biggest kept candidate, plus kept candidates whose name matches the fire
             (fires_master) and are >= 10% of its size; other = remaining kept candidates

Output: data/annotations/hbb_selection.gpkg, layers `candidates` and `fires`, in EPSG:3577
(one layer must hold every fire; the build reprojects each fire back to its own UTM grid).
Refuses to overwrite: once it exists it's hand-edited work. --append-new adds only fires not
already in it.

    python scripts/hbb_candidates.py [--fire 1920-26,...] [--append-new]
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyogrio

from _registry import FIRES_MASTER, ROOT, load_fires, parse_fire_arg

SEASONS = ROOT / "registry" / "seasons"
OUT = ROOT / "data" / "annotations" / "hbb_selection.gpkg"
CRS = 3577                       # GDA94 / Australian Albers, display + storage only
MIN_HA = 0.5                     # drop slivers left by the AOI clip
OVERLAP = 0.5                    # same group if overlap >= 50% of the smaller candidate
STOP = {"fire", "complex", "road", "the", "creek", "river", "national", "park", "mount",
        "nsw", "act", "vic", "tas", "qld", "and", "wildfire", "bushfire"}


def season_of(code: str) -> str:
    y = 2000 + int(code[:2])
    return f"{y}-{str(y + 1)[2:]}"


def to_date(v):
    """HBB dates come as datetimes, 'YYYYMMDD' strings, or nulls."""
    if v is None or v is pd.NaT or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, pd.Timestamp):
        return None if pd.isna(v) else v.date()
    s = str(v).strip()
    if re.fullmatch(r"\d{8}", s):
        return date(int(s[:4]), int(s[4:6]), int(s[6:]))
    try:
        t = pd.Timestamp(s)
        return None if pd.isna(t) else t.date()
    except (ValueError, TypeError):
        return None


def words(s) -> set[str]:
    return {w for w in re.split(r"[^a-z]+", str(s).lower()) if len(w) > 2 and w not in STOP}


def stack_dates(fire) -> tuple[date, date] | None:
    """Pre and final dates of the stacks actually on disk."""
    pre = [d for d, r in fire.dates if r == "pre" and (fire.folder / f"{d}_pre.tif").exists()]
    fin = [d for d, r in fire.dates if r == "final" and (fire.folder / f"{d}_final.tif").exists()]
    return (pre[0], fin[0]) if pre and fin else None


def timing(ign, ext, pre, fin) -> str:
    if ign and ign > fin:
        return "after final"
    if ext and ext < pre:
        return "before pre"
    if ign is None:
        return "no date"
    if ign < pre:
        if ext:
            return "spans pre"
        # no end date: assume it was out by the pre date if it started > 2 weeks before
        return "before pre" if (pre - ign).days > 14 else "spans pre?"
    return "in window"


def candidates_for(fire, fire_name: str, pre: date, fin: date) -> gpd.GeoDataFrame | None:
    geom = fire.geometry
    parts = []
    for s in (season_of(fire.fire_code), "unknown_date"):
        p = SEASONS / f"bushfire_boundaries_{s}.gpkg"
        if p.exists():
            x = pyogrio.read_dataframe(p, bbox=geom.bounds)
            if len(x):
                parts.append(x)
    if not parts:
        return None
    d = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), geometry="geometry", crs=parts[0].crs)
    aoi = gpd.GeoSeries([geom], crs=4326).to_crs(d.crs).iloc[0]
    d = d[d.intersects(aoi)].copy()
    if d.empty:
        return None

    d = d.to_crs(CRS)
    aoi = gpd.GeoSeries([geom], crs=4326).to_crs(CRS).iloc[0]
    d["geometry"] = d.geometry.make_valid()
    d["full_ha"] = d.area / 1e4
    for c in ("ignition_date", "capture_date", "extinguish_date"):
        d[c] = d[c].map(to_date).astype(object)
    d["fire_name"] = d["fire_name"].fillna("(unnamed)")
    d["key"] = d["agency"].fillna("?") + "|" + d["fire_name"] + "|" + d["ignition_date"].astype(str)
    d["n_records"] = d.key.map(d.key.value_counts())
    first = lambda s: s.iloc[0]  # noqa: E731
    latest = lambda s: max((x for x in s if x), default=None)  # noqa: E731
    g = d.dissolve(by="key", aggfunc={
        "agency": first, "fire_name": first, "fire_type": first, "ignition_date": first,
        "capture_date": latest, "extinguish_date": latest, "capt_method": first, "state": first,
        "full_ha": "sum", "n_records": first}).reset_index(drop=True)
    g = gpd.GeoDataFrame(g, geometry="geometry", crs=CRS)
    g["geometry"] = g.geometry.intersection(aoi)
    g["area_ha"] = g.area / 1e4
    g = g[g.area_ha >= MIN_HA].reset_index(drop=True)
    g["clipped_pct"] = (100 * (1 - g.area_ha / g.full_ha.clip(lower=1e-9))).clip(0, 100).round(0)

    # overlap groups (union-find), numbered by total area
    parent = list(range(len(g)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    geoms = list(g.geometry)
    for i, a in enumerate(geoms):
        for j in g.sindex.query(a, predicate="intersects"):
            if j > i and a.intersection(geoms[j]).area / max(1, min(a.area, geoms[j].area)) >= OVERLAP:
                parent[find(i)] = find(j)
    roots = pd.Series([find(i) for i in range(len(g))])
    rank = g.area_ha.groupby(roots).max().rank(ascending=False, method="first").astype(int)
    g["group"] = roots.map(rank).values
    g["n_in_group"] = g.group.map(g.group.value_counts())

    g["timing"] = [timing(i, e, pre, fin) for i, e in zip(g.ignition_date, g.extinguish_date)]
    g["burning_after_final"] = [bool(e and e > fin) for e in g.extinguish_date]
    g["latest_date"] = [max([x for x in (i, c, e) if x], default=None)
                        for i, c, e in zip(g.ignition_date, g.capture_date, g.extinguish_date)]

    # suggestion (metadata only)
    usable = ~g.timing.isin(["before pre", "after final"])
    sugg = pd.Series("drop", index=g.index)
    for _, grp in g[usable].groupby("group"):
        ranked = grp.assign(_d=grp.latest_date.map(lambda x: x or date.min)).sort_values(
            ["_d", "area_ha"], ascending=False)
        covered = None
        for i, r in ranked.iterrows():
            new = r.geometry if covered is None else r.geometry.difference(covered)
            if covered is None or new.area / max(1, r.geometry.area) > 0.5:
                sugg[i] = "keep"
                covered = r.geometry if covered is None else covered.union(r.geometry)
    kept = sugg == "keep"
    name_w = words(fire_name)
    # target = name matches (ignoring fragments < 10% of the biggest kept) + the biggest kept;
    # HBB names often differ from the common name (Waroona = "Murray Road", KI = "Ravine")
    big = g.area_ha[kept].max() if kept.any() else 0
    match = kept & g.fire_name.map(lambda n: bool(words(n) & name_w)) & (g.area_ha >= 0.1 * big)
    if kept.any():
        match[g.area_ha[kept].idxmax()] = True
    sugg[kept] = "other"
    sugg[match] = "target"
    g["suggested"] = sugg

    g["fire_code"] = fire.fire_code
    g["fire_id"] = fire.fire_id
    g = g.sort_values(["group", "area_ha"], ascending=[True, False]).reset_index(drop=True)
    g["cand_id"] = [f"{fire.fire_code}-{n:03d}" for n in range(1, len(g) + 1)]
    g["role"] = None
    g["note"] = None
    g = g.rename(columns={"fire_name": "hbb_name"})
    for c in ("ignition_date", "capture_date", "extinguish_date", "latest_date"):
        g[c] = g[c].map(lambda x: x.isoformat() if x else None)
    g["area_ha"] = g.area_ha.round(1)
    g["full_ha"] = g.full_ha.round(1)
    cols = ["cand_id", "fire_code", "fire_id", "role", "note", "suggested", "group", "n_in_group",
            "hbb_name", "agency", "state", "fire_type", "timing", "ignition_date", "extinguish_date",
            "capture_date", "latest_date", "burning_after_final", "capt_method", "area_ha", "full_ha",
            "clipped_pct", "n_records", "geometry"]
    return gpd.GeoDataFrame(g[cols], geometry="geometry", crs=CRS)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fire", help="fire_codes, comma-separated (default: every fire with stacks, "
                                   "excluding the 2025-26 holdout)")
    ap.add_argument("--append-new", action="store_true",
                    help="add fires not yet in an existing hbb_selection.gpkg; never touches existing rows")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    existing: set[str] = set()
    if args.out.exists():
        if not args.append_new:
            sys.exit(f"{args.out} exists (hand-edited work) -- refusing to overwrite. "
                     f"Use --append-new to add fires only.")
        existing = set(pyogrio.read_dataframe(args.out, layer="fires", read_geometry=False).fire_code)

    master = pd.read_csv(FIRES_MASTER, encoding="utf-8-sig", dtype=str).set_index("fire_code")
    fires = load_fires()
    codes = parse_fire_arg(args.fire) or [c for c in sorted(fires) if not c.startswith("2526")]
    cands, rows = [], []
    for code in codes:
        f = fires[code]
        if code in existing:
            print(f"{code}: already in {args.out.name}, skipped")
            continue
        dates = stack_dates(f) if f.ok else None
        if not dates:
            print(f"{code}: no pre + final stacks on disk, skipped")
            continue
        pre, fin = dates
        name = master.at[code, "fire_name"]
        c = candidates_for(f, name, pre, fin)
        n = c.suggested.value_counts().to_dict() if c is not None else {}
        print(f"{code} {f.fire_id:<50} {0 if c is None else len(c):3d} candidates  {n}")
        if c is not None:
            cands.append(c)
        rows.append(dict(fire_code=code, fire_id=f.fire_id, fire_name=name, pre_date=pre.isoformat(),
                         final_date=fin.isoformat(), n_candidates=0 if c is None else len(c),
                         include=None, post_ok=None, label_quality=None, note=None, geometry=f.geometry))
    if not rows:
        print("nothing to write")
        return
    fl = gpd.GeoDataFrame(rows, geometry="geometry", crs=4326).to_crs(CRS)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    mode = dict(append=True) if existing else {}
    if cands:
        pyogrio.write_dataframe(pd.concat(cands, ignore_index=True), args.out, layer="candidates", **mode)
    pyogrio.write_dataframe(fl, args.out, layer="fires", **mode)
    print(f"wrote {args.out}: {len(fl)} fires, {sum(map(len, cands))} candidates")


if __name__ == "__main__":
    main()
