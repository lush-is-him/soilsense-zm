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
python -m backend.set_password admin        # optional: choose an easier password
```

`backend.seed` creates three starting accounts and prints their passwords once: `admin`, `officer` (a demo extension officer) and `farmer` (a demo self-testing farmer). To choose the passwords yourself, set `SEED_ADMIN_PASSWORD`, `SEED_OFFICER_PASSWORD` and `SEED_FARMER_PASSWORD` first; see `.env.example`.

## Who uses it (accounts and roles)

| Role | How they get an account | What they see and do |
|---|---|---|
| **Farmer** | Signs up on the login page ("Create an account") | Only their own fields. Guided soil test with animated steps, live probe reading, plain advice. Asks for a lab test or an officer visit when unsure. Edits their own profile (village, language, SMS, sharing). |
| **Extension / lab officer** | The admin creates a named account | Farmers who share their results, farmers they registered, and anyone who asked for help. Works the request list, enters lab results (which gives the farmer high-confidence advice), sees the soil map, tests for farmers without a phone. Sees the rule tables. |
| **Admin** | Seeded; can create more | Everything: overview numbers, map of all fields, accounts (create, deactivate, reset passwords), probe calibrations. |

An unusual reading (very high or low pH, or far from the soil map) is flagged *check the probe* until a repeat reading agrees; then *confirm with a lab test*. A database from before November 2026 is migrated automatically when the server starts: `operator` and `agronomist` become officers and keep their passwords.

## Run

```
$env:SOILSENSE_SECRET_KEY = "any-long-random-text"
uvicorn backend.main:app --reload
```

Open http://localhost:8000 for the dashboard (the map page needs internet for its background map) and http://localhost:8000/docs for the API. To use it from a phone on the same Wi-Fi, run with `--host 0.0.0.0` and open `http://<laptop IP>:8000`. Phone GPS only works over HTTPS or on localhost, so for field tests use a tunnel or a certificate.

## Probe

Wiring, firmware upload, calibration and buffers: [`firmware/README.md`](firmware/README.md).

```
pip install -r bridge\requirements.txt
python -m bridge.bridge calibrate --board ph4502c --device probe-1
python -m bridge.bridge read --board ph4502c --device probe-1 --field 1
python -m bridge.bridge live --field 1     # demo: keeps reading; the dashboard Live page shows pH and advice
```

**Live demo: double-click `START_DEMO.bat`** (in the project folder; right-click > Send to > Desktop to put a shortcut on the desktop). It starts the server in a second window, opens the dashboard, offers to calibrate, and runs the probe program. In the dashboard open a field and press **Live probe reading**: the probe follows that field. Put the probe in a sample; the page shows the pH while it settles, saves the reading and shows the advice. Rinse, next sample, it repeats. Close both black windows to stop.

The pH is corrected for the sample's own temperature (from the DS18B20). The moisture sensor is no longer used.

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
