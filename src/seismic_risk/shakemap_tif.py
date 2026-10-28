"""Convert the HayWired ShakeMap grid.xml into a multi-band GeoTIFF.

grid.xml lists one row per grid node (LON LAT PGA PGV MMI PSA03 PSA10 PSA30), with
nodes running from lon_min..lon_max and lat_max..lat_min inclusive. The nodes are
cell centers, so the GeoTIFF's top-left corner sits half a cell up and left of the
first node. Values are written unchanged, in the units grid.xml declares.

python -m seismic_risk.shakemap_tif  ->  data/interim/haywired_shakemap.tif
"""
import re
import zipfile
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "data/raw/haywired_shakemap/grid.xml.zip"
OUT = ROOT / "data/interim/haywired_shakemap.tif"
NODATA = -9999.0


def read_grid(path=SRC):
    z = zipfile.ZipFile(path)
    xml = z.read(z.namelist()[0]).decode()
    spec = dict(re.findall(r'(\w+)="([^"]*)"', re.search(r"<grid_specification[^>]*>", xml).group(0)))
    fields = re.findall(r'<grid_field index="(\d+)" name="(\w+)" units="(\w+)"', xml)
    names = [n for _, n, _ in sorted(fields, key=lambda f: int(f[0]))]
    units = {n: u for _, n, u in fields}
    body = xml.split("<grid_data>")[1].split("</grid_data>")[0]
    data = np.array(body.split(), dtype="float64").reshape(-1, len(names))
    return spec, names, units, data


def to_arrays(spec, names, data):
    nlon, nlat = int(spec["nlon"]), int(spec["nlat"])
    if data.shape[0] != nlon * nlat:
        raise ValueError(f"{data.shape[0]} rows, expected {nlon * nlat}")
    lon, lat = data[:, 0].reshape(nlat, nlon), data[:, 1].reshape(nlat, nlon)
    # Rows go north to south, columns west to east. Check rather than assume.
    if not (np.all(np.diff(lat[:, 0]) < 0) and np.all(np.diff(lon[0]) > 0)):
        raise ValueError("grid.xml is not ordered north-to-south, west-to-east")
    dx = (float(spec["lon_max"]) - float(spec["lon_min"])) / (nlon - 1)
    dy = (float(spec["lat_max"]) - float(spec["lat_min"])) / (nlat - 1)
    transform = from_origin(float(spec["lon_min"]) - dx / 2, float(spec["lat_max"]) + dy / 2, dx, dy)
    bands = {n: data[:, i].reshape(nlat, nlon) for i, n in enumerate(names) if n not in ("LON", "LAT")}
    return bands, transform


def main():
    spec, names, units, data = read_grid()
    bands, transform = to_arrays(spec, names, data)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    first = next(iter(bands.values()))
    with rasterio.open(OUT, "w", driver="GTiff", width=first.shape[1], height=first.shape[0],
                       count=len(bands), dtype="float32", crs="EPSG:4326", transform=transform,
                       nodata=NODATA, compress="deflate") as dst:
        for i, (name, arr) in enumerate(bands.items(), start=1):
            dst.write(arr.astype("float32"), i)
            dst.set_band_description(i, name)
            dst.update_tags(i, units=units[name])
        dst.update_tags(source="USGS ShakeMap ushaywiredm7.05_se v33 grid.xml",
                        shakemap_version=spec.get("shakemap_version", "33"))
    print(f"{OUT.relative_to(ROOT)}: {len(bands)} bands {list(bands)}, "
          f"{first.shape[1]}x{first.shape[0]}, cell {transform.a:.6f} deg")


if __name__ == "__main__":
    main()
