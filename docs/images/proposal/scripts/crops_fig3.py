"""Cut pre/post crops around screened blobs and coarse candidates, with HBB outlines in pixel coords."""
import sys, pickle, numpy as np, rasterio, geopandas as gpd, pyogrio
from rasterio.enums import Resampling
from shapely.geometry import box
from shapely.affinity import affine_transform
D = sys.argv[1]; N = 400
c = gpd.GeoDataFrame(pyogrio.read_dataframe('data/annotations/hbb_selection.gpkg', layer='candidates'))
fires = pyogrio.read_dataframe('data/annotations/hbb_selection.gpkg', layer='fires').set_index('fire_code')
blobs = pickle.load(open(f'{D}/blobs.pkl', 'rb'))
# blobs: top-k per fire/kind
jobs = []
for kind, k in (('miss', 3), ('over', 2)):
    by = {}
    for b in blobs:
        if b['kind'] == kind: by.setdefault(b['fire'], []).append(b)
    for fc, bs in by.items():
        for b in sorted(bs, key=lambda x: -x['ha'])[:k]:
            if b['ha'] >= 100: jobs.append((fc, f"{kind} {b['ha']} ha", b['geometry'], b['geometry']))
for cid in sys.argv[2].split(','):
    row = c[c.cand_id == cid].iloc[0]
    jobs.append((row.fire_code, f'coarse {cid}', None, cid))
out = []
for fc, title, g, ref in jobs:
    f = fires.loc[fc]; d = f'data/fires/{f.fire_id}'
    with rasterio.open(f'{d}/{f.final_date}_final.tif') as s:
        crs, tr = s.crs, s.transform
    cf = c[c.fire_code == fc].to_crs(crs)
    if g is None:
        g = cf[cf.cand_id == ref].geometry.iloc[0]
        x0, y0, x1, y1 = g.bounds; side = max(x1 - x0, y1 - y0) * 1.1
    else:
        x0, y0, x1, y1 = g.bounds; side = max(max(x1 - x0, y1 - y0) * 3, 6000)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    bb = box(cx - side / 2, cy - side / 2, cx + side / 2, cy + side / 2)
    win = rasterio.windows.from_bounds(*bb.bounds, transform=tr).round_offsets().round_lengths()
    imgs = {}
    for role, date in (('pre', f.pre_date), ('final', f.final_date)):
        with rasterio.open(f'{d}/{date}_{role}.tif') as s:
            a = s.read([1, 2, 3], window=win, out_shape=(3, N, N), resampling=Resampling.average, boundless=True, fill_value=0).astype(float)
            a += float(s.tags(1).get('BOA_ADD_OFFSET', 0))
        imgs[role] = a.astype(np.float32)
    wtr = rasterio.windows.transform(win, tr) * rasterio.Affine.scale(win.width / N)
    inv = ~wtr; M = [inv.a, inv.b, inv.d, inv.e, inv.xoff, inv.yoff]
    def rings(geom):
        geom = geom.intersection(bb.buffer(side * 0.05))
        if geom.is_empty: return []
        geom = affine_transform(geom, M); rs = []
        for p in getattr(geom, 'geoms', [geom]):
            if p.geom_type != 'Polygon': continue
            rs.append(np.array(p.exterior.coords)); rs += [np.array(i.coords) for i in p.interiors]
        return rs
    hbb = []
    for _, k in cf.iterrows():
        r = rings(k.geometry)
        if r: hbb.append(dict(cand=k.cand_id, name=k.hbb_name, agency=k.agency, sug=k.suggested, timing=k.timing, rings=r))
    blob = rings(g) if not title.startswith('coarse') else []
    out.append(dict(fire=fc, fire_id=f.fire_id, title=title, km=win.width * 0.02, pre=imgs['pre'], post=imgs['final'],
                    hbb=hbb, blob=blob, dates=(f.pre_date, f.final_date),
                    center=(cx, cy), crs=str(crs)))
    print(fc, title, f'{win.width*0.02:.1f} km', flush=True)
pickle.dump(out, open(f'{D}/crops.pkl', 'wb'))
