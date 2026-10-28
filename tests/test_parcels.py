import pytest

from seismic_risk.parcels import normalize_block_lot, normalize_parcel


@pytest.mark.parametrize("raw, expected", [
    ("1829001", "1829001"),
    ("0121012", "0121012"),
    ("170243", "1702043"),       # soft-story row with an unpadded lot
    ("1634018A", "1634018A"),    # lot suffix
    ("0463A017", "0463A017"),    # block suffix
    ("0463a-017", "0463A017"),
    ("0463A/017", "0463A017"),
    ("SF2480002B", "2480002B"),  # footprint mblr
    ("CN4712008", "4712008"),
    (" 3538026a ", "3538026A"),
])
def test_normalize_parcel(raw, expected):
    assert normalize_parcel(raw) == expected


@pytest.mark.parametrize("raw", [None, "", float("nan"), "SM005123290", "SFVACSTART1", "12AB"])
def test_normalize_parcel_rejects(raw):
    assert normalize_parcel(raw) is None


@pytest.mark.parametrize("block, lot, expected", [
    ("1702", "43", "1702043"),
    ("121", "10", "0121010"),
    ("0463A", "017", "0463A017"),
    ("1634", "018a", "1634018A"),
    ("1634", None, None),
    ("ABCD", "001", None),
])
def test_normalize_block_lot(block, lot, expected):
    assert normalize_block_lot(block, lot) == expected
