PY := .venv/bin/python

.PHONY: all setup download inventory pipeline test

all: pipeline test

setup:
	python3 -m venv .venv
	$(PY) -m pip install -r requirements.txt
	$(PY) -m pip install -e .

download:
	$(PY) -m seismic_risk.download

inventory:
	$(PY) -m seismic_risk.shakemap_tif
	$(PY) -m seismic_risk.inventory > docs/data_inventory.json

pipeline:
	$(PY) -m seismic_risk

test:
	$(PY) -m pytest -q
