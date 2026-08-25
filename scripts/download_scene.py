"""Download a Sentinel-2 20m stack (B12, B11, B8A, SCL) for Georges Yard,
single tile (56HKG), for one date."""
from pathlib import Path
import rasterio
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds
from pystac_client import Client

BBOX = (150.2642, -35.1414, 150.5413, -34.9902)
FIRE = "georges_yard"
TILE = "56HKG"
OUT_DIR = Path("data/raw") / FIRE

ASSETS = ["swir22", "swir16", "nir08", "scl"]   # B12, B11, B8A, SCL
NAMES  = ["B12", "B11", "B8A", "SCL"]

# edit this per run
DATE  = "2019-12-21"   # or "2019-12-21"
LABEL = "prefire"      # or "postfire"


def fetch_date(date_str: str, label: str):
    cat = Client.open("https://earth-search.aws.element84.com/v1")
    items = list(cat.search(
        collections=["sentinel-2-l2a"],
        bbox=BBOX,
        datetime=f"{date_str}/{date_str}",
    ).items())

    tile_items = [i for i in items if TILE in i.id]
    if not tile_items:
        raise RuntimeError(f"No {TILE} scene found for {date_str}")
    item = min(tile_items, key=lambda i: i.properties.get("eo:cloud_cover", 100))
    print(f"{date_str}: using {item.id} "
          f"({item.properties.get('eo:cloud_cover'):.0f}% cloud)")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dst_path = OUT_DIR / f"{FIRE}_{date_str}_{label}_20m.tif"

    band_arrays, profile = {}, None

    for asset_key, name in zip(ASSETS, NAMES):
        with rasterio.open(item.assets[asset_key].href) as src:
            l, b, r, t = transform_bounds("EPSG:4326", src.crs, *BBOX)
            win = from_bounds(l, b, r, t, src.transform).round_offsets().round_lengths()
            arr = src.read(1, window=win)
            band_arrays[name] = arr
            if profile is None:
                profile = dict(
                    driver="GTiff", height=arr.shape[0], width=arr.shape[1],
                    count=len(NAMES), dtype="uint16", crs=src.crs,
                    transform=src.window_transform(win),
                    tiled=True, blockxsize=512, blockysize=512,
                    compress="deflate", predictor=2,
                )

    with rasterio.open(dst_path, "w", **profile) as dst:
        for i, name in enumerate(NAMES, start=1):
            dst.write(band_arrays[name].astype("uint16"), i)
            dst.set_band_description(i, name)

    with open(dst_path.with_suffix(".txt"), "w") as f:
        f.write(f"scene: {item.id}\ndate: {date_str}\n")

    print("wrote", dst_path)


if __name__ == "__main__":
    fetch_date(DATE, LABEL)