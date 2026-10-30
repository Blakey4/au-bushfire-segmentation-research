"""Add all kept in-window HBB perimeters (suggested target + other fires) to fig1.npz."""
import sys, numpy as np, rasterio, geopandas as gpd, pyogrio
from rasterio.features import rasterize
NPZ = sys.argv[1]; c0, r0, w, h = 1200, 1300, 640, 640
z = dict(np.load(NPZ))
with rasterio.open('data/fires/1920-orroral-valley/2020-03-15_final.tif') as s:
    crs, tr = s.crs, s.transform
c = gpd.GeoDataFrame(pyogrio.read_dataframe('data/annotations/hbb_selection.gpkg', layer='candidates'))
c = c[(c.fire_code == '1920-26') & c.suggested.isin(['target', 'other']) & (c.timing == 'in window')].to_crs(crs)
print(c[['hbb_name', 'agency', 'area_ha']].to_string())
ftr = tr * rasterio.Affine.scale(2)
ctr = rasterio.windows.transform(rasterio.windows.Window(c0, r0, w, h), tr)
z['hbb_all_full'] = np.stack([rasterize([(g, 1)], out_shape=z['full'].shape[1:], transform=ftr).astype(bool) for g in c.geometry])
z['hbb_all_crop'] = rasterize(((g, 1) for g in c.geometry), out_shape=(h, w), transform=ctr).astype(bool)
z['hbb_all_crop_each'] = np.stack([rasterize([(g, 1)], out_shape=(h, w), transform=ctr).astype(bool) for g in c.geometry])
np.savez_compressed(NPZ, **z)
