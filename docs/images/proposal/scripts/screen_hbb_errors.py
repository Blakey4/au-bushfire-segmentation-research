"""Screen the 18 zero-shot fires for possible HBB errors: coarse geometry, burnt area outside any
HBB record (miss), and large unchanged areas inside the target (over). dNBR here is only a pointer
for finding examples to inspect by eye, never a label."""
import sys, json, numpy as np, rasterio, geopandas as gpd, pyogrio, pandas as pd
from rasterio.enums import Resampling
from rasterio.features import rasterize, shapes, sieve
from shapely.geometry import shape
FAC = 2; PX_HA = (20 * FAC) ** 2 / 1e4
c = gpd.GeoDataFrame(pyogrio.read_dataframe('data/annotations/hbb_selection.gpkg', layer='candidates'))
fires = pyogrio.read_dataframe('data/annotations/hbb_selection.gpkg', layer='fires')

def read(path):
    with rasterio.open(path) as s:
        H, W = s.height // FAC, s.width // FAC
        b = s.read([3, 1], out_shape=(2, H, W), resampling=Resampling.average).astype(float)
        scl = s.read(5, out_shape=(H, W), resampling=Resampling.nearest)
        off = float(s.tags(1).get('BOA_ADD_OFFSET', 0))
        tr, crs = s.transform * rasterio.Affine.scale(FAC), s.crs
    b += off
    nbr = (b[0] - b[1]) / np.maximum(b[0] + b[1], 1)
    return nbr, scl, tr, crs

def blobs(mask, tr, min_ha):
    m = sieve(mask.astype(np.uint8), int(min_ha / PX_HA), connectivity=8)
    out = []
    for g, v in shapes(m, mask=m.astype(bool), transform=tr):
        p = shape(g)
        if p.area / 1e4 >= min_ha:
            out.append(p)
    return out

rows, geo = [], []
for _, f in fires.iterrows():
    d = f'data/fires/{f.fire_id}'
    a, sa, tr, crs = read(f'{d}/{f.pre_date}_pre.tif')
    b, sb, _, _ = read(f'{d}/{f.final_date}_final.tif')
    dn = a - b
    valid = ~np.isin(sa, (0, 3, 8, 9, 10, 6)) & ~np.isin(sb, (0, 3, 8, 9, 10, 6))
    cf = c[c.fire_code == f.fire_code].to_crs(crs)
    sh = dn.shape
    R = lambda gs: rasterize(((g, 1) for g in gs), out_shape=sh, transform=tr).astype(bool) if len(gs) else np.zeros(sh, bool)
    T = R(cf[cf.suggested == 'target'].geometry)
    ANY = R(cf.geometry.buffer(200))
    # coarseness of kept candidates
    for _, k in cf[cf.suggested.isin(['target', 'other'])].iterrows():
        g = k.geometry; polys = getattr(g, 'geoms', [g])
        nv = sum(len(p.exterior.coords) + sum(len(i.coords) for i in p.interiors) for p in polys)
        per = g.length / 1000
        rows.append(dict(kind='geom', fire=f.fire_code, fire_id=f.fire_id, cand=k.cand_id, name=k.hbb_name,
                         agency=k.agency, capt=k.capt_method, area_ha=round(k.area_ha), n_vert=nv,
                         seg_m=round(per * 1000 / max(nv, 1)), over_frac=None))
    tv = T & valid
    over = (dn[tv] < 0.1).mean() if tv.any() else np.nan
    rows.append(dict(kind='fire', fire=f.fire_code, fire_id=f.fire_id, area_ha=round(tv.sum() * PX_HA),
                     over_frac=round(float(over), 3), valid_frac=round(float(valid[T].mean()), 3) if T.any() else None))
    for p in blobs((dn > 0.27) & valid & ~ANY, tr, 30):
        geo.append(dict(fire=f.fire_code, kind='miss', ha=round(p.area / 1e4), geometry=p))
    for p in blobs((dn < 0.05) & valid & T, tr, 100):
        geo.append(dict(fire=f.fire_code, kind='over', ha=round(p.area / 1e4), geometry=p))
    print(f.fire_code, f.fire_id, 'done', flush=True)
df = pd.DataFrame(rows); df.to_csv(sys.argv[1] + '/screen.csv', index=False)
gpd.GeoDataFrame(geo, geometry='geometry', crs=None).assign(geometry=lambda x: x.geometry.apply(lambda g: g.wkt)).drop(columns='geometry') if False else None
import pickle; pickle.dump(geo, open(sys.argv[1] + '/blobs.pkl', 'wb'))
