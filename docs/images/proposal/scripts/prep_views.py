"""Read every annotation view of one fire (protocol 5.2), downsampled for a side-by-side image."""
import sys, glob, os, numpy as np, rasterio
from rasterio.enums import Resampling
d, OUT, MAXPX = sys.argv[1], sys.argv[2], int(sys.argv[3])
pre = glob.glob(f'{d}/*_pre.tif')[0]; fin = glob.glob(f'{d}/*_final.tif')[0]
with rasterio.open(fin) as s:
    f = max(s.width, s.height) / MAXPX; shp = (int(s.height / f), int(s.width / f))
def rd(path, bands, rs=Resampling.average):
    with rasterio.open(path) as s:
        a = s.read(bands, out_shape=(len(bands),) + shp, resampling=rs, masked=True).astype(float)
        offs = [float(s.tags(b).get('BOA_ADD_OFFSET', 0)) for b in bands]
    return np.stack([a[i].filled(np.nan) + offs[i] for i in range(len(bands))])
out = {'pre_date': os.path.basename(pre)[:10], 'final_date': os.path.basename(fin)[:10]}
for role, p in (('pre', pre), ('final', fin)):
    out[f'atm_{role}'] = rd(p, [1, 2, 3]); out[f'swir_{role}'] = rd(p, [1, 3, 4])
date = out['final_date']
out['nbr_final'] = rd(f'{d}/{date}_nbr.tif', [1])[0]
out['nbr2_final'] = rd(f'{d}/{date}_nbr2.tif', [1])[0]
out['dnbr'] = rd(f'{d}/dnbr.tif', [1])[0]
for h in ('atm-pen-highlight', 'swir-highlight'):
    with rasterio.open(f'{d}/{h}.tif') as s:
        out[h] = s.read([1, 2, 3], out_shape=(3,) + shp, resampling=Resampling.average)
np.savez_compressed(OUT, **out); print(OUT, shp)
