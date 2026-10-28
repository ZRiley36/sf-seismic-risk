"""Run the whole pipeline: python -m seismic_risk [step ...]

Steps run in order. Name steps to run only those, e.g. `python -m seismic_risk score analyze`.
Downloading is separate (python -m seismic_risk.download) because it only needs to happen once.
"""
import sys
import time
import warnings

from seismic_risk import analyze, clean, hazards, ingest, join, raster, score, shakemap_tif, spotcheck

warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

STEPS = {
    "shakemap": shakemap_tif.main,
    "ingest": ingest.main,
    "clean": clean.main,
    "join": join.main,
    "raster": raster.main,
    "hazards": hazards.main,
    "score": score.main,
    "analyze": analyze.main,
    "spotcheck": spotcheck.main,
}


def main(argv):
    unknown = set(argv) - set(STEPS)
    if unknown:
        sys.exit(f"unknown steps: {', '.join(sorted(unknown))}. Choose from {', '.join(STEPS)}")
    start = time.time()
    for name, fn in STEPS.items():
        if argv and name not in argv:
            continue
        t = time.time()
        print(f"{name}")
        fn()
        print(f"  ({time.time() - t:.0f}s)")
    print(f"done in {time.time() - start:.0f}s")


if __name__ == "__main__":
    main(sys.argv[1:])
