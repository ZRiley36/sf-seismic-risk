"""SF assessor parcel IDs (block/lot), normalized to one string format.

The canonical form is BBBB[X]LLL[Y]: a 4-digit block with an optional letter suffix,
then a 3-digit lot with an optional letter suffix, uppercase, no separators.
Examples: "0463A017", "1634018A", "1702043".

Sources disagree on padding and prefixes: the soft-story list has a few lots
written without leading zeros ("170243"), footprints prefix the ID with "SF" or
"CN", and some files use separators like "0463A-017" or "0463A/017".
"""
import re

import pandas as pd

_BLOCK = re.compile(r"^(\d{1,4})([A-Z]?)$")
_LOT = re.compile(r"^(\d{1,3})([A-Z]?)$")


def _clean(s):
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return None
    s = re.sub(r"[\s\-/._]", "", str(s).upper())
    return s or None


def normalize_block_lot(block, lot):
    """Pad a separate block and lot. Returns None if either part doesn't look like one."""
    b, l = _clean(block), _clean(lot)
    if not b or not l:
        return None
    mb, ml = _BLOCK.match(b), _LOT.match(l)
    if not mb or not ml:
        return None
    return f"{int(mb.group(1)):04d}{mb.group(2)}{int(ml.group(1)):03d}{ml.group(2)}"


def normalize_parcel(parcel):
    """Normalize a combined block+lot string.

    A string of digits is split as a 4-digit block plus the rest as the lot, which is
    how SF writes them. "170243" becomes block 1702, lot 043. Strings that can't be
    split unambiguously that way return None rather than a guess.
    """
    p = _clean(parcel)
    if not p:
        return None
    p = re.sub(r"^(SF|CN)", "", p)
    m = re.match(r"^(\d{4})([A-Z]?)(\d{1,3})([A-Z]?)$", p)
    if not m:
        return None
    return f"{m.group(1)}{m.group(2)}{int(m.group(3)):03d}{m.group(4)}"
