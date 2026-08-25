"""Compute dNBR between pre/post fire scenes and write both the raw
dNBR raster (for visual inspection) and thresholded seed polygons."""
import numpy as np
import rasterio
import geopandas as gpd
from rasterio.features import shapes
from shapely.geometry import shape

PRE  = "data/raw/georges_yard/georges_yard_2019-11-21_prefire_20m.tif"
POST = "data/raw/georges_yard/georges_yard_2019-12-21_prefire_20m.tif"
OUT_DIR = "data/derived/georges_yard"

THRESH = 0.27          # Key & Benson "moderate-low" cut — tune by eye later
MIN_AREA_M2 = 20_000    # drop specks under 2 ha


def nbr(path):
    with rasterio.open(path) as src:
        b12 = src.read(1).astype("float32") / 10000  # SWIR2
        b8a = src.read(3).astype("float32") / 10000   # NIR
        return (b8a - b12) / (b8a + b12 + 1e-6), src.transform, src.crs, src.profile


nbr_pre, tf, crs, prof = nbr(PRE)
nbr_post, _, _, _ = nbr(POST)
dnbr = nbr_pre - nbr_post

# 1. write raw dNBR raster for visual inspection in QGIS
import os
os.makedirs(OUT_DIR, exist_ok=True)
dnbr_path = f"{OUT_DIR}/georges_yard_dnbr.tif"
prof.update(count=1, dtype="float32", compress="deflate")
with rasterio.open(dnbr_path, "w", **prof) as dst:
    dst.write(dnbr.astype("float32"), 1)
print("wrote", dnbr_path)

# 2. threshold -> polygons
mask = (dnbr > THRESH).astype("uint8")
geoms = [shape(g) for g, v in shapes(mask, mask=mask.astype(bool), transform=tf) if v == 1]

gdf = gpd.GeoDataFrame(geometry=geoms, crs=crs)
gdf = gdf[gdf.area > MIN_AREA_M2]
gdf["geometry"] = gdf.simplify(20)
gdf = gdf.dissolve().explode(index_parts=False)
gdf["fire"] = "georges_yard"
gdf["class"] = "burnt"
gdf["method"] = "dnbr_seed"
gdf["confidence"] = "medium"

seed_path = f"{OUT_DIR}/seed.gpkg"
gdf.to_file(seed_path, layer="seed", driver="GPKG")
print(f"wrote {len(gdf)} seed polygon(s) to {seed_path}")