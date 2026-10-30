"""Shared registry access for the download / index scripts.

Joins `registry/aoi.gpkg` (bbox + scouted dates, keyed by fire_code) to
`registry/fires_master.csv` (fire_id), parses the `--fire` argument, and validates each
fire's dates. Read-only: nothing here writes to the registry.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
AOI_GPKG = ROOT / "registry" / "aoi.gpkg"
FIRES_MASTER = ROOT / "registry" / "fires_master.csv"
SCENES_CSV = ROOT / "registry" / "scenes.csv"
FIRES_DIR = ROOT / "data" / "fires"


@dataclass
class Fire:
    fire_code: str
    fire_id: str | None
    geometry: object                      # shapely geometry, EPSG:4326
    dates: list[tuple[date, str]] = field(default_factory=list)   # (date, role) sorted by date
    problems: list[str] = field(default_factory=list)             # -> fire is skipped
    warnings: list[str] = field(default_factory=list)             # -> printed, fire still runs

    @property
    def ok(self) -> bool:
        return not self.problems

    @property
    def folder(self) -> Path:
        return FIRES_DIR / self.fire_id


def parse_fire_arg(value: str | None) -> list[str] | None:
    """'1920-01, 1920-02' -> ['1920-01', '1920-02']; None -> None (= all fires)."""
    if not value:
        return None
    return [c.strip() for c in value.split(",") if c.strip()]


def _as_date(v) -> date | None:
    """aoi.gpkg dates arrive as datetimes/Timestamps, ISO strings, or d/m/yy text."""
    if v is None or (isinstance(v, float) and pd.isna(v)) or v is pd.NaT:
        return None
    if isinstance(v, (datetime, pd.Timestamp)):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v).strip()
    if not s or s.lower() == "nan":
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    raise ValueError(s)


def _season_window(fire_code: str) -> tuple[date, date] | None:
    """'1920-03' -> fire season 1 Jul 2019 .. 30 Jun 2020 (loose sanity window only)."""
    m = re.match(r"^(\d{2})(\d{2})-", fire_code)
    if not m:
        return None
    y0 = 2000 + int(m.group(1))
    return date(y0, 7, 1), date(y0 + 1, 6, 30)


def load_fires() -> dict[str, Fire]:
    """All AOIs, keyed by fire_code, validated. Duplicate codes are kept as one entry with a problem."""
    aoi = gpd.read_file(AOI_GPKG, layer="aoi")
    uncoded = aoi["fire_code"].isna() | (aoi["fire_code"].astype(str).str.strip() == "")
    if uncoded.any():
        print(f"note: ignoring {int(uncoded.sum())} aoi.gpkg row(s) with no fire_code")
        aoi = aoi[~uncoded]
    if aoi.crs is None or aoi.crs.to_epsg() != 4326:
        aoi = aoi.to_crs(4326)
    master = pd.read_csv(FIRES_MASTER, encoding="utf-8-sig", dtype=str)
    code_to_id = dict(zip(master["fire_code"].str.strip(), master["fire_id"].str.strip()))

    fires: dict[str, Fire] = {}
    counts = aoi["fire_code"].value_counts()
    for _, row in aoi.iterrows():
        code = str(row["fire_code"]).strip()
        f = Fire(code, code_to_id.get(code), row.geometry)

        if counts[code] > 1:
            f.problems.append(f"fire_code appears {counts[code]}x in aoi.gpkg (clean up duplicates)")
        if f.fire_id is None:
            f.problems.append("fire_code not found in fires_master.csv (no fire_id)")
        if row.geometry is None or row.geometry.is_empty:
            f.problems.append("no AOI geometry")

        dates: list[tuple[date, str]] = []
        try:
            pre = _as_date(row.get("prefire_date"))
            post = _as_date(row.get("postfire_date"))
        except ValueError as e:
            f.problems.append(f"unparseable pre/post date {e}")
            pre = post = None
        if pre:
            dates.append((pre, "pre"))
        if post:
            dates.append((post, "final"))
        if pre and post and pre >= post:
            f.problems.append(f"prefire_date {pre} is not before postfire_date {post} (likely a typo)")

        during_raw = row.get("during_dates")
        if during_raw is not None and not (isinstance(during_raw, float) and pd.isna(during_raw)):
            for tok in re.split(r"[;,\s]+", str(during_raw).strip()):
                if not tok:
                    continue
                try:
                    d = _as_date(tok)
                except ValueError:
                    f.problems.append(f"unparseable during date '{tok}' (use YYYY-MM-DD or d/m/yy)")
                    continue
                if (pre and d <= pre) or (post and d >= post):
                    f.warnings.append(f"during date {d} is not between pre and post")
                dates.append((d, "during"))

        if not dates:
            f.problems.append("no dates scouted yet")

        win = _season_window(code)
        if win:
            odd = [d for d, r in dates if r != "pre" and not (win[0] <= d <= win[1])]
            if odd:
                f.warnings.append(f"date(s) {', '.join(map(str, odd))} fall outside the "
                                  f"{win[0].year}-{str(win[1].year)[2:]} season implied by the code")

        f.dates = sorted(dict((d, r) for d, r in dates).items())
        if code in fires:                       # duplicate: keep the first, it's skipped anyway
            continue
        fires[code] = f
    return fires


def select_fires(fire_arg: str | None) -> list[Fire]:
    """
    --fire given: exactly those codes; unknown codes or invalid fires are a hard error.
    --fire omitted: every AOI; invalid ones are reported and skipped.
    """
    fires = load_fires()
    codes = parse_fire_arg(fire_arg)
    if codes is None:
        for f in fires.values():
            if not f.ok:
                print(f"SKIP {f.fire_code}: {'; '.join(f.problems)}")
        return [f for f in fires.values() if f.ok]

    missing = sorted(set(codes) - set(fires))
    if missing:
        raise SystemExit(f"fire_code(s) not found in aoi.gpkg: {missing}")
    bad = [f for c in codes if not (f := fires[c]).ok]
    if bad:
        raise SystemExit("cannot process:\n" + "\n".join(
            f"  {f.fire_code}: {'; '.join(f.problems)}" for f in bad))
    return [fires[c] for c in dict.fromkeys(codes)]
