"""Figure 1 arrays: Orroral full post scene + valley crop (pre / post / 4 Feb during), HBB + dNBR masks."""
import sys; sys.path.insert(0, 'scripts'); sys.path.insert(0, 'data/fires/1920-orroral-valley/review/scripts')
from datetime import date
import numpy as np, rasterio, geopandas as gpd
from rasterio.enums import Resampling
from rasterio.features import rasterize
from pystac_client import Client
from _registry import load_fires
import download_scenes as ds
OUT = sys.argv[1]
FIRE = 'data/fires/1920-orroral-valley'
c0, r0, w, h = [int(x) for x in sys.argv[2].split(',')]
win = rasterio.windows.Window(c0, r0, w, h)

def rgb(path, window=None, fac=1):
    with rasterio.open(path) as s:
        wi = window or rasterio.windows.Window(0, 0, s.width, s.height)
        a = s.read([1, 2, 3], window=wi, out_shape=(3, int(wi.height // fac), int(wi.width // fac)),
                   resampling=Resampling.average).astype(float)
        a += float(s.tags(1).get('BOA_ADD_OFFSET', 0))
        return a, s.window_transform(wi) * rasterio.Affine.scale(fac), s.crs, (s.height, s.width)

full, ftr, crs, shp = rgb(f'{FIRE}/2020-03-15_final.tif', fac=2)
pre, ctr, _, _ = rgb(f'{FIRE}/2019-12-16_pre.tif', win)
post, _, _, _ = rgb(f'{FIRE}/2020-03-15_final.tif', win)

def nbr(path, window):
    with rasterio.open(path) as s:
        b = s.read([3, 1, 5], window=window).astype(float)   # B8A, B12, SCL
        off = float(s.tags(1).get('BOA_ADD_OFFSET', 0))
    n, sw = b[0] + off, b[1] + off
    return (n - sw) / np.maximum(n + sw, 1), b[2]

nb_pre, scl_pre = nbr(f'{FIRE}/2019-12-16_pre.tif', win)
nb_post, scl_post = nbr(f'{FIRE}/2020-03-15_final.tif', win)

# 4 Feb during image straight from Earth Search, on the same grid
f = load_fires()['1920-26']
cat = Client.open(ds.EARTH_SEARCH)
d = date(2020, 2, 4)
its = ds.find_items(cat, f.geometry, d, 'sentinel-2-l2a', crs.to_epsg())
offs, _ = ds.decide_offsets(its, f.geometry)
shift = {i.id: offs[i.id][0] for i in its}
with rasterio.Env(**ds.GDAL_ENV):
    bands = {b: ds.mosaic_band(its, b, 20, b == 'SCL', crs.to_epsg(), ctr, w, h, shift).astype(float)
             for b in ('B12', 'B11', 'B8A', 'SCL')}
dur = np.stack([bands['B12'], bands['B11'], bands['B8A']])
nb_dur = (bands['B8A'] - bands['B12']) / np.maximum(bands['B8A'] + bands['B12'], 1)

sel = gpd.read_file(f'{FIRE}/review_hbb_selection.gpkg').to_crs(crs)
tgt = sel[sel.role == 'target'].geometry
hbb_crop = rasterize(((g, 1) for g in tgt), out_shape=(h, w), transform=ctr).astype(bool)
hbb_full = rasterize(((g, 1) for g in tgt), out_shape=full.shape[1:], transform=ftr).astype(bool)
cloud = lambda s: np.isin(s, (3, 8, 9, 10))
dnbr_post = nb_pre - nb_post
dnbr_dur = nb_pre - nb_dur
ok_post = ~cloud(scl_pre) & ~cloud(scl_post)
ok_dur = ~cloud(scl_pre) & ~cloud(bands['SCL'])
# 'valley' = the bright dry-grass floor in the pre image inside the HBB polygon
bright = pre.mean(0) > 2600
v = hbb_crop & bright
print(f'valley px {v.sum()} ({v.sum()*0.04:.0f} ha)')
print(f'  post  dNBR>0.1: {100*(dnbr_post[v & ok_post] > 0.1).mean():.0f}%  median {np.median(dnbr_post[v & ok_post]):.2f}')
print(f'  4 Feb dNBR>0.1: {100*(dnbr_dur[v & ok_dur] > 0.1).mean():.0f}%  median {np.median(dnbr_dur[v & ok_dur]):.2f}  (cloud-free {100*ok_dur[v].mean():.0f}%)')
print('items', [i.id for i in its])
np.savez_compressed(OUT, full=full, pre=pre, post=post, dur=dur, hbb_crop=hbb_crop, hbb_full=hbb_full,
                    dnbr_post=dnbr_post, dnbr_dur=dnbr_dur, ok_post=ok_post, ok_dur=ok_dur, valley=v,
                    box=np.array([c0 / 2, r0 / 2, w / 2, h / 2]))
