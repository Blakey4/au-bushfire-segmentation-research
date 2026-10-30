"""Figure 2 arrays: per fire, square crop around the HBB target, pre / post atm-pen + label (0 unburnt, 1 burnt, 2 ignored)."""
import sys
import numpy as np, rasterio, geopandas as gpd, pyogrio
from rasterio.enums import Resampling
from rasterio.features import rasterize
OUT, N = sys.argv[1], int(sys.argv[2])
c = gpd.GeoDataFrame(pyogrio.read_dataframe('data/annotations/hbb_selection.gpkg', layer='candidates'))
fires = pyogrio.read_dataframe('data/annotations/hbb_selection.gpkg', layer='fires')
role = c.role.fillna(c.suggested)
res = {}
sel_codes = sys.argv[3].split(',') if len(sys.argv) > 3 else None
for _, f in fires.iterrows():
    if sel_codes and f.fire_code not in sel_codes: continue
    d = f'data/fires/{f.fire_id}'
    with rasterio.open(f'{d}/{f.final_date}_final.tif') as s:
        crs, tr, H, W = s.crs, s.transform, s.height, s.width
    cf = c[c.fire_code == f.fire_code].to_crs(crs)
    r = role[cf.index]
    tgt = cf[r == 'target']
    x0, y0, x1, y1 = tgt.total_bounds
    col0, row0 = ~tr * (x0, y1); col1, row1 = ~tr * (x1, y0)
    side = int(max(col1 - col0, row1 - row0) * 1.08)
    side = min(side, H, W)
    cc, rc = (col0 + col1) / 2, (row0 + row1) / 2
    co = int(np.clip(cc - side / 2, 0, W - side)); ro = int(np.clip(rc - side / 2, 0, H - side))
    win = rasterio.windows.Window(co, ro, side, side)
    out = {}
    for role_, date in (('pre', f.pre_date), ('final', f.final_date)):
        with rasterio.open(f'{d}/{date}_{role_}.tif') as s:
            a = s.read([1, 2, 3, 5], window=win, out_shape=(4, N, N), resampling=Resampling.average).astype(float)
            sc = s.read(5, window=win, out_shape=(N, N), resampling=Resampling.nearest)
            a[:3] += float(s.tags(1).get('BOA_ADD_OFFSET', 0))
        out[role_] = a[:3].astype(np.float32); out[role_ + '_scl'] = sc
    wtr = rasterio.windows.transform(win, tr) * rasterio.Affine.scale(side / N)
    lab = np.zeros((N, N), np.uint8)
    oth = cf[r == 'other']
    if len(oth):
        lab[rasterize(((g, 1) for g in oth.geometry), out_shape=(N, N), transform=wtr).astype(bool)] = 2
    lab[rasterize(((g, 1) for g in tgt.geometry), out_shape=(N, N), transform=wtr).astype(bool)] = 1
    cl = np.isin(out['pre_scl'], (3, 8, 9, 10)) | np.isin(out['final_scl'], (3, 8, 9, 10))
    lab[cl] = 3
    for k, v in out.items():
        res[f'{f.fire_code}|{k}'] = v
    res[f'{f.fire_code}|label'] = lab
    res[f'{f.fire_code}|km'] = np.array(side * 0.02)
    print(f.fire_code, f.fire_id, f'{side*0.02:.0f} km', f'burnt {100*(lab==1).mean():.0f}%')
np.savez_compressed(OUT, **res)
