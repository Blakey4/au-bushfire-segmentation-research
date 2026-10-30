"""Extra comparison views (not in the protocol 5.2 locked set): RBR and BAIS2 rasters.

Writes into data/fires/<fire_id>/:
    rbr.tif                 dNBR / (NBR(pre) + 1.001)                         float32
    <date>_bais2.tif        BAIS2 for every downloaded date (Filipponi 2018)  float32
                            (1 - sqrt(B06*B07*B8A / B04)) * ((B12 - B8A) / sqrt(B12 + B8A) + 1)

NBR uses B8A (narrow NIR, 20 m) like make_indices.py; the stacks have no B8. The agriculture
(B11/B8A/B02) and false-colour IR (B8A/B04/B03) composites are QGIS styles, not files.
Existing outputs are skipped unless --overwrite.

Usage:
    python scripts/make_extra_views.py --fire 1920-26,1920-09
"""
from __future__ import annotations

import argparse

import numpy as np

from _registry import select_fires
from make_indices import norm_diff, read_reflectance, write_float


def bais2(r):
    with np.errstate(divide="ignore", invalid="ignore"):
        veg = 1 - np.sqrt(r["B06"] * r["B07"] * r["B8A"] / r["B04"])
        return veg * ((r["B12"] - r["B8A"]) / np.sqrt(r["B12"] + r["B8A"]) + 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fire", required=True, help="comma-separated fire_codes")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()
    for fire in select_fires(args.fire):
        d = fire.folder
        print(f"{fire.fire_code} -> {fire.fire_id}")
        stacks = {p.name[:10]: p for p in sorted(d.glob("*_pre.tif")) + sorted(d.glob("*_final.tif"))}
        refl = {}
        for date, p in stacks.items():
            refl[date], prof = read_reflectance(p)
            out = d / f"{date}_bais2.tif"
            if out.exists() and not args.overwrite:
                print(f"    skip {out.name} (exists)")
                continue
            write_float(out, bais2(refl[date]), prof, dict(VIEW="bais2", FIRE_ID=fire.fire_id, DATE=date))
        pre = next(p.name[:10] for p in d.glob("*_pre.tif"))
        fin = next(p.name[:10] for p in d.glob("*_final.tif"))
        out = d / "rbr.tif"
        if out.exists() and not args.overwrite:
            print(f"    skip {out.name} (exists)")
            continue
        nbr_pre = norm_diff(refl[pre]["B8A"], refl[pre]["B12"])
        dnbr = nbr_pre - norm_diff(refl[fin]["B8A"], refl[fin]["B12"])
        write_float(out, dnbr / (nbr_pre + 1.001), prof,
                    dict(VIEW="rbr", FIRE_ID=fire.fire_id, PRE_DATE=pre, FINAL_DATE=fin))


if __name__ == "__main__":
    main()
