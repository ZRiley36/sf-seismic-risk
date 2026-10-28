import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import Point, box

from seismic_risk.raster import sample_points, zonal
from seismic_risk.shakemap_tif import to_arrays

CELL = 0.5


@pytest.fixture
def tif(tmp_path):
    """3x4 two-band grid. Cell (row r, col c) holds 10*r + c in band 1 and 100 + 10*r + c in band 2."""
    path = tmp_path / "t.tif"
    rows, cols = 3, 4
    v = np.add.outer(10 * np.arange(rows), np.arange(cols)).astype("float32")
    with rasterio.open(path, "w", driver="GTiff", width=cols, height=rows, count=2, dtype="float32",
                       crs="EPSG:4326", transform=from_origin(-122.0, 38.0, CELL, CELL), nodata=-9999) as d:
        d.write(v, 1)
        d.write(v + 100, 2)
        d.set_band_description(1, "MMI")
        d.set_band_description(2, "PGA")
    return path


def center(r, c):
    return Point(-122.0 + (c + 0.5) * CELL, 38.0 - (r + 0.5) * CELL)


def test_known_pixel_gives_known_value(tif):
    s = sample_points([center(2, 3), center(0, 0), center(1, 2)], tif)
    assert list(s["MMI"]) == [23, 0, 12]
    assert list(s["PGA"]) == [123, 100, 112]
    assert s["cell"] == ["2_3", "0_0", "1_2"]


def test_point_near_cell_edge_stays_in_its_cell(tif):
    p = Point(-122.0 + 2 * CELL - 1e-6, 38.0 - 1.5 * CELL)  # just west of the col 1 / col 2 edge
    assert sample_points([p], tif)["MMI"][0] == 11


def test_zonal_inside_one_cell_matches_point(tif):
    c = center(1, 1)
    z = zonal([box(c.x - 0.01, c.y - 0.01, c.x + 0.01, c.y + 0.01)], tif)
    assert z["MMI_zonal_mean"] == [11] and z["MMI_zonal_max"] == [11]


def test_zonal_across_an_edge_averages_both_cells(tif):
    x = -122.0 + 2 * CELL  # edge between cols 1 and 2
    y = 38.0 - 1.5 * CELL
    z = zonal([box(x - 0.01, y - 0.01, x + 0.01, y + 0.01)], tif)
    assert z["MMI_zonal_mean"] == [11.5] and z["MMI_zonal_max"] == [12] and z["zonal_cells"] == [2]


def test_grid_nodes_become_cell_centers():
    """grid.xml nodes are cell centers: the first node must land in the middle of pixel (0, 0)."""
    spec = {"nlon": "3", "nlat": "2", "lon_min": "-123.0", "lon_max": "-122.0",
            "lat_min": "37.0", "lat_max": "38.0"}
    lon, lat = np.meshgrid([-123.0, -122.5, -122.0], [38.0, 37.0])
    data = np.column_stack([lon.ravel(), lat.ravel(), np.arange(6.0)])
    bands, t = to_arrays(spec, ["LON", "LAT", "MMI"], data)
    assert bands["MMI"].tolist() == [[0, 1, 2], [3, 4, 5]]
    assert t @ (0.5, 0.5) == pytest.approx((-123.0, 38.0))
    assert t @ (2.5, 1.5) == pytest.approx((-122.0, 37.0))


def test_grid_out_of_order_is_rejected():
    spec = {"nlon": "2", "nlat": "2", "lon_min": "0", "lon_max": "1", "lat_min": "0", "lat_max": "1"}
    data = np.array([[0, 0, 1], [1, 0, 2], [0, 1, 3], [1, 1, 4]], dtype=float)  # south-to-north
    with pytest.raises(ValueError):
        to_arrays(spec, ["LON", "LAT", "MMI"], data)
