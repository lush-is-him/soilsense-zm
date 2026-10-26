# SoilSense ZM

Rule-based soil and crop advice for smallholder farmers in Shimabala, Kafue District, Zambia. A low-cost probe measures soil pH; the system checks it against the free iSDAsoil map to decide how far to trust the map, then gives Plan A (fix the soil), Plan B (cheaper route) and Plan C (crops that suit the soil now). No machine learning.

The design is in [`docs/SOILSENSE_SPEC.md`](docs/SOILSENSE_SPEC.md); progress is in [`docs/MIGRATION_PLAN.md`](docs/MIGRATION_PLAN.md).

## Folders

| Folder | What it holds |
|---|---|
| `engine/` | The decision logic: quality check, map lookup, trust level, rule engine. No web or database code |
| `rules/` | Every agronomy value, as YAML with its source (see `rules/README.md`) |
| `backend/` | FastAPI app, database migrations, login |
| `dashboard/` | The web dashboard (plain HTML, CSS, JavaScript) |
| `i18n/` | User-facing text in English (Nyanja and Tonga to come) |
| `scripts/` | Download the iSDAsoil layers; run the scenario suite |
| `tests/` | Automated tests |
| `analysis/` | Dissertation analysis scripts and figures (not part of the product) |
| `data/` | Local database and map layers (not in git) |

## Set up (Windows PowerShell)

```
cd "C:\Users\USER\SoilSense ZM"
pip install -r backend\requirements.txt -r requirements-dev.txt
python scripts\fetch_isdasoil.py --boundary "tiff files\gadm41_ZMB.gpkg"
python -m backend.seed
```

`backend.seed` creates the users `operator`, `agronomist` and `admin` and prints their passwords once. To choose them yourself, set `SEED_OPERATOR_PASSWORD` (and the others) first; see `.env.example`.

## Run

```
$env:SOILSENSE_SECRET_KEY = "any-long-random-text"
uvicorn backend.main:app --reload
```

Open http://localhost:8000 for the dashboard and http://localhost:8000/docs for the API. To use it from a phone on the same Wi-Fi, run with `--host 0.0.0.0` and open `http://<laptop IP>:8000`. Phone GPS only works over HTTPS or on localhost, so for field tests use a tunnel or a certificate.

## Probe

Wiring, firmware upload, calibration and buffers: [`firmware/README.md`](firmware/README.md).

```
pip install -r bridge\requirements.txt
python -m bridge.bridge calibrate --port COM3 --board ph4502c --device probe-1
python -m bridge.bridge read --port COM3 --board ph4502c --device probe-1 --field 1
```

## Waiting on others

[`docs/WAITING_ON.md`](docs/WAITING_ON.md) lists every outside input (agronomist answers, lab results, reviewers, buffers, weighing) and the file or command it goes into.

## Test

```
python -m pytest
python -m engine.validate              # rule tables valid? which values are still OPEN?
python scripts\run_scenarios.py        # docs\scenarios\scenarios.csv for the reviewer (RQ3)
python scripts\run_scenarios.py --compare-methods
```

Tests marked `xfail` are expected to fail: each names an agronomy value that has not been supplied yet (spec section 7).
