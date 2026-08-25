from pystac_client import Client

BBOX = (150.2642, -35.1414, 150.5413, -34.9902)

cat = Client.open("https://earth-search.aws.element84.com/v1")
items = list(cat.search(
    collections=["sentinel-2-l2a"],
    bbox=BBOX,
    datetime="2019-11-01/2020-01-15",
    query={"eo:cloud_cover": {"lt": 90}},
).items())

for i in sorted(items, key=lambda x: x.datetime):
    print(i.datetime.date(), f"{i.properties.get('eo:cloud_cover'):.0f}% cloud", i.id)