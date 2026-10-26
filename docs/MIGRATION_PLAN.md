# SoilSense ZM — Migration Plan

> **Audit date:** 2026-10-26  
> **Spec version:** audited against v0.1; reviewed against v0.2 (25 Oct 2026, `docs/SOILSENSE_SPEC.md`), see section 11  
> **Auditor:** Antigravity (Phase 1, read-only)

---

## 1. Summary (10 lines)

The codebase is a working ML-based soil classifier with a FastAPI backend and a polished dark-mode dashboard. **Roughly 40% of the infrastructure can be reused** (FastAPI scaffold, dashboard shell, farmer CRUD, SMS stub, database connection pattern). **The entire advisory and prediction pipeline must be replaced**: the system currently classifies soil into four ML-predicted labels (Healthy / Moderate / Degraded / Critical) and returns hardcoded English-only advice, whereas the spec requires a rule-based engine driven by YAML data, three plans (A/B/C), map agreement, trust levels, and trilingual output.

**What must go:** All ML code, models, training scripts, synthetic data, pickle files, and the `scikit-learn`/`joblib`/`numpy`/`pandas` backend dependencies. The entire `advisory.py` (205 lines of hardcoded agronomy text) violates spec rule 3 ("rules are data, not code").

**Biggest risks:** (1) The advisory engine is the heart of the product and must be built from scratch with the YAML rule data. (2) The database schema has only 2 tables vs. the spec's 13+ — a full redesign is needed. (3) No Arduino firmware or serial bridge exists anywhere in the repo. (4) No auth, no roles, no i18n, no quality checker, no map service, no trust checker — all are missing.

---

## 2. Repo state

- **Repository:** Initialized on `main`, tracked to public GitHub repo `https://github.com/lush-is-him/soilsense-zm`.
- **Base commit:** `195280a` (Clean working tree, initial commit of all source files, documentation, and spec).
- **Ignored assets:** GeoTIFF rasters (`tiff files/` > 1.1GB, exceeding GitHub 100MB limit) and local SQLite `.db` / `__pycache__` excluded via `.gitignore`.


---

## 3. Stack inventory

| Item | Detail |
|---|---|
| **Languages** | Python (backend), HTML/CSS/JS (dashboard), no Arduino code |
| **Backend framework** | FastAPI (Python), run via `uvicorn backend.main:app --reload` |
| **Database** | SQLite (`backend/soilsense.db`, 20 KB), created inline by `database.py` on import, no migrations |
| **Dashboard** | Vanilla HTML + CSS + JS, served as static files by FastAPI at `/dashboard`, loads Chart.js 4.4.4 from CDN |
| **ML** | scikit-learn RandomForestClassifier, trained on 2,000 synthetic samples, pickled as `soil_model_v2.pkl` (2.6 MB) and `label_encoder_v2.pkl` |
| **Dependency file** | `backend/requirements.txt` (fastapi, uvicorn, joblib, numpy, pandas, scikit-learn, africastalking) |
| **Tests** | **None** — no test files, no test framework in requirements |
| **i18n** | **None** — all text is English-only, hardcoded in Python and HTML |
| **Arduino firmware** | **Not present anywhere in the repo** |
| **Serial bridge** | **Not present anywhere in the repo** |
| **GeoTIFF rasters** | `tiff files/` — 7 SoilGrids 2.0 files (pH, clay, sand, silt, SOC, CEC, BDOD) at 0–5 cm depth, plus `gadm41_ZMB.gpkg` (Kafue boundary). These are SoilGrids, **not iSDAsoil** |

### Folder structure (two levels)

```
SoilSense ZM/
├── backend/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app entry
│   ├── models.py               # Pydantic schemas
│   ├── database.py             # SQLite setup (2 tables)
│   ├── advisory.py             # Hardcoded advisory engine (ML labels → text)
│   ├── sms.py                  # Africa's Talking stub
│   ├── requirements.txt
│   ├── soilsense.db            # SQLite database (20 KB)
│   └── routes/
│       ├── __init__.py
│       ├── predict.py          # /predict endpoint (loads ML model)
│       └── farmers.py          # /farmers CRUD
├── dashboard/
│   ├── index.html              # SPA shell
│   ├── app.js                  # API integration, charts
│   └── style.css               # Dark-mode design system (1000 lines)
├── dissertation/
│   ├── SOILSENSE_SPEC.md
│   └── ANTIGRAVITY_AUDIT_PROMPT.md
├── plots/                      # ML training visualisations (5 PNG files)
├── tiff files/                 # SoilGrids GeoTIFFs (7 files, ~1.2 GB total)
├── train_model.py              # ML: train RandomForest
├── generate_training_data.py   # ML: create synthetic CSV
├── check_ph.py                 # Analysis: pH stats from CSV
├── extract_kafue.py            # Analysis: sample SoilGrids for Kafue
├── make_charts.py              # Analysis: dissertation figures
├── make_kafue_map.py           # Analysis: pH scatter map
├── soil_model_v2.pkl           # Trained model (2.6 MB)
├── soil_model.pkl              # Older model (1.8 MB)
├── label_encoder_v2.pkl        # Label encoder
├── label_encoder.pkl           # Older encoder
├── synthetic_training_data.csv # Older training data
├── synthetic_training_data_v2.csv  # Current training data (2,000 rows)
└── kafue_soil_data.csv         # Extracted SoilGrids data (500 rows)
```

### Secret check

Files containing API key references, phone numbers, or credentials (paths only, **no values printed**):

| File | What |
|---|---|
| `backend/sms.py` | Reads `AT_USERNAME`, `AT_API_KEY`, `AT_SENDER_ID` from environment variables. **No hardcoded key values** — defaults are `"sandbox"` and `""`. Safe. |
| `backend/models.py` | `farmer_phone` field in the `SoilReading` schema |
| `backend/routes/predict.py` | Passes `farmer_phone` to SMS function |
| `backend/routes/farmers.py` | Stores and displays `phone` (no consent or deletion mechanism) |
| `backend/database.py` | `phone TEXT NOT NULL UNIQUE` in `farmers` table — stored permanently, no consent field, no deletion mechanism. **Violates NFR5.** |
| `dashboard/app.js` | Displays phone numbers in the farmer directory table |
| `dashboard/index.html` | Phone input field for SMS |

**WARNING: Phone numbers are stored with no consent field and no deletion mechanism. NFR5 requires consent and deletion after demonstrations.**

---

## 4. Component verdict table

| Component | Path(s) | Verdict | What matches the spec | What does not | Effort | Track & Sprint |
|---|---|---|---|---|---|---|
| **ML code, models, training scripts, sensor-only soil classifier** | `train_model.py`, `generate_training_data.py`, `soil_model*.pkl`, `label_encoder*.pkl`, `synthetic_training_data*.csv`, `plots/`, `backend/routes/predict.py` (ML parts), `backend/requirements.txt` (sklearn, joblib, numpy, pandas) | **DELETE** | Nothing — spec rule 6 says "No ML anywhere" | Everything: RandomForest classifier, synthetic data pipeline, pickle models, ML prediction endpoint | **M** | A, Sprint 1 (S1-1) |
| **Database schema and migrations** | `backend/database.py`, `backend/soilsense.db` | **REPLACE** | SQLite is a reasonable choice; `farmers` and `readings` tables exist | Only 2 tables (spec needs 13+); no migrations; `readings` stores ML prediction, not replicates/quality/calibration; no `users`, `fields`, `calibrations`, `map_estimates`, `lab_results`, `field_checks`, `recommendations`, `rules`, `recommendation_rules`, `sms_messages`, `devices` tables; phone stored with no consent column | **L** | A, Sprint 1 (S1-2) |
| **Users, roles, login, password hashing** | None | **MISSING** | — | No auth, no `users` table, no roles, no password hashing, no login endpoint | **M** | A, Sprint 1 (S1-2) |
| **Farmer and field registration, GPS handling** | `backend/routes/farmers.py`, `backend/models.py` | **ADAPT** | `POST /farmers` and `GET /farmers/{id}` exist with CRUD; farmer name, phone, location fields present | Farmer schema uses `name` not `alias`; phone is mandatory (spec: nullable); no `preferred_language`, no `sms_consent`; location is freetext not lat/lon; no `fields` table; no GPS accuracy, no 30 m rule, no manual pin, no `location_source` | **M** | A, Sprint 1 (S1-3) |
| **Arduino firmware** | None | **MISSING** | — | No firmware, no `.ino` files anywhere in the repo | **L** | B, Sprint 1 (S1-4) |
| **Serial bridge** | None | **MISSING** | — | No bridge code, no `POST /readings` by device | **M** | B, Sprint 1 (S1-4) |
| **Probe calibration** | None | **MISSING** | — | No calibration endpoint, no `calibrations` table, no buffer check, no slope validation | **M** | B, Sprint 1 (S1-4) |
| **Reading quality check** | None | **MISSING** | — | No `QualityChecker`, no replicate check, no slope check, no temperature check, no implausible pH check | **M** | D, Sprint 1 (S1-5) |
| **Map service (iSDAsoil)** | `extract_kafue.py`, `tiff files/` | **ADAPT** | Raster extraction code exists and works; `extract_kafue.py` samples GeoTIFFs correctly; Kafue boundary extraction works; CRS transformation handled | Uses **SoilGrids** not **iSDAsoil**; uses 0–5 cm not 0–20 cm; no SD layer (spec needs `ph_sd`); extracts all 500 points at once (batch), not per-field lookup; no `MapService` class; no API endpoint | **M** | E, Sprint 2 |
| **Trust checker** | None | **MISSING** | — | No map agreement rule, no trust levels, no `E_PROBE` config | **M** | E, Sprint 2 |
| **Rule engine** | `backend/advisory.py` | **REPLACE** | The file produces advisory output (right concept) | All agronomy values are hardcoded strings in Python (violates spec rule 3); classifies into Healthy/Moderate/Degraded/Critical (not spec's pH bands); no YAML rules; no fired rule tracking; no Plans A/B/C; no crop selection logic; no lime rate by texture; no method sensitivity; no `as_of_date` | **L** | D, Sprint 1 (S1-7) |
| **Translation and i18n** | None | **MISSING** | — | Everything is English only; no language files; no `reviewed` flag; no language switch mechanism | **M** | F, Sprint 2 |
| **Household measures** | None | **MISSING** | — | No conversion code, no `measures.yaml` | **S** | G, Sprint 3 |
| **SMS delivery (Africa's Talking)** | `backend/sms.py` | **ADAPT** | Africa's Talking integration is correct and well-structured; reads credentials from env vars (good); sandbox mode works; `format_advisory_sms` truncates to 160 chars | No consent check before sending; no `sms_messages` table for audit; phone not checked for consent flag; sends based on ML prediction text, needs to send plan-based advice; no phone deletion mechanism | **S** | G, Sprint 3 |
| **Dashboard: pages, mobile, low-bandwidth** | `dashboard/index.html`, `dashboard/app.js`, `dashboard/style.css` | **ADAPT** | Mobile-responsive layout exists; dark mode looks good; form for readings; farmer directory; charts; modals; toast notifications; view switcher (Farmer/Officer) | No login screen; no language switch; no field registration; no GPS capture; no advice view with Plans A/B/C; no trust level display; no "why this advice" panel; no sampling help screen; loads Chart.js from CDN (bandwidth concern); no unreviewed marker; no field checks form; no lab entry; shows ML labels not spec concepts | **L** | C, Sprint 1 (S1-6) |
| **Automated tests** | None | **MISSING** | — | No test files, no pytest/unittest in requirements, no test configuration | **L** | All tracks |
| **Configuration and environment handling** | `backend/sms.py` (env vars) | **ADAPT** | SMS config reads from env vars correctly | No `.env` file; no config module; no `E_PROBE`, `PH_WATER_MINUS_CACL2`, temperature range, or other spec config values; DB path is hardcoded | **S** | A, Sprint 0 |
| **Analysis scripts** | `extract_kafue.py`, `check_ph.py`, `make_charts.py`, `make_kafue_map.py` | **N/A (not part of product)** | Useful for dissertation figures and understanding raster data | Hardcoded paths; uses SoilGrids not iSDAsoil; `extract_kafue.py` has reusable raster extraction logic | — | Move to `analysis/` |

---

## 5. Findings from the 10 specific checks

### Check 1: Remaining ML or model code

**Extensive ML code remains — this is the core of the current system.**

| File | ML dependency |
|---|---|
| `train_model.py` (L19–25) | `sklearn.model_selection`, `sklearn.ensemble.RandomForestClassifier`, `sklearn.metrics`, `sklearn.preprocessing.LabelEncoder` |
| `train_model.py` (L18, 192–193) | `joblib.dump()` to save model |
| `generate_training_data.py` | Creates synthetic training data (numpy, pandas) |
| `backend/routes/predict.py` (L9, 29–30) | `joblib.load()` to load model and encoder |
| `backend/routes/predict.py` (L63–66) | `model.predict()`, `model.predict_proba()`, `label_encoder.inverse_transform()` |
| `backend/requirements.txt` (L3–6) | `joblib>=1.3.0`, `numpy>=1.24.0`, `pandas>=2.0.0`, `scikit-learn>=1.3.0` |
| `backend/main.py` (L29, 72–77) | Description mentions "Random Forest ML model"; root endpoint checks `model_loaded` |
| `backend/advisory.py` (entire file) | Takes ML label as input (`soil_health: str` = Healthy/Moderate/Degraded/Critical) |
| `soil_model.pkl`, `soil_model_v2.pkl` | Trained RandomForest pickle files |
| `label_encoder.pkl`, `label_encoder_v2.pkl` | Label encoder pickle files |
| `synthetic_training_data.csv`, `synthetic_training_data_v2.csv` | Synthetic training data |
| `plots/` (5 PNG files) | ML training visualisations (confusion matrix, feature importance, etc.) |

**Dependencies on ML:** The entire `/predict` endpoint, the advisory engine (`advisory.py`), the root endpoint status check, the dashboard's prediction flow, and the Pydantic schemas (`PredictionResponse`, `Advisory`) all depend on ML output.

### Check 2: Agronomy values hardcoded in code

**Massive violation of spec rule 3.** The file `backend/advisory.py` contains 200+ lines of hardcoded agronomy text:

| File:Line | Hardcoded value |
|---|---|
| `advisory.py:31` | "pH is within the optimal range (6.0–7.5)" |
| `advisory.py:35` | "Compound D (10-20-10) at 200 kg/ha" |
| `advisory.py:36` | "Urea (46-0-0) at 200 kg/ha 4–6 weeks after emergence" |
| `advisory.py:37` | "organic manure (2–3 tonnes/ha)" |
| `advisory.py:40` | "expected yield 5–8 tonnes/ha" |
| `advisory.py:64` | "lime at 1–2 tonnes/ha to raise pH above 5.8" |
| `advisory.py:70` | "Compound D at 200 kg/ha" |
| `advisory.py:71` | "Urea at 250 kg/ha in two splits" |
| `advisory.py:72` | "SSP at 100 kg/ha" |
| `advisory.py:73` | "manure at 3–5 tonnes/ha" |
| `advisory.py:100` | "lime at 2–4 tonnes/ha" |
| `advisory.py:107–111` | "Compound D at 200 kg/ha", "Urea at 300 kg/ha", "SSP at 150 kg/ha", "MOP at 50 kg/ha", "5+ tonnes/ha cattle manure" |
| `advisory.py:144` | "lime at 4–6 tonnes/ha" |
| `advisory.py:146` | "two doses: 3 tonnes/ha now, 3 tonnes/ha next season" |
| `advisory.py:155–156` | "Compound D at 200 kg/ha + Urea at 250 kg/ha + SSP at 200 kg/ha" |
| `advisory.py:187–202` | pH-based lime rates: "1–2 tonnes/ha" at 5.5+, "2–4 tonnes/ha" at 4.5+, "4–6 tonnes/ha" below 4.5 |
| `advisory.py:39–46` | Crop list: Maize, Soybeans, Groundnuts, Sunflower, Wheat, Vegetables (doesn't match spec crop list) |
| `advisory.py:114–121` | Crop list includes Cassava, Sweet potatoes, Finger millet, Pineapple (not in spec) |

Additionally, many lime rates in `advisory.py` **do not match** the spec's `rules/lime.yaml` rates (which depend on pH band × texture), and the crop lists include crops outside the spec scope (Wheat, Vegetables, Cassava, Sweet potatoes, Pineapple, Cowpeas).

### Check 3: Database schema vs spec

**Current schema (2 tables):**

```sql
-- farmers
id, name, phone (NOT NULL UNIQUE), location, district, farm_size_hectares,
created_at, updated_at

-- readings
id, farmer_id (FK), pH, moisture, temperature, nitrogen, phosphorus,
organic_carbon, prediction, confidence, advisory, latitude, longitude,
created_at
```

**Spec requires 13+ tables.** Missing entirely:

| Missing table | Consequence |
|---|---|
| `users` | No auth, no roles |
| `fields` | Readings tied to farmers not fields; no GPS with accuracy/source |
| `devices` | No device tracking |
| `calibrations` | No calibration history |
| `map_estimates` | No map data storage |
| `lab_results` | No lab entry |
| `field_checks` | No field checks |
| `recommendations` | No structured advice storage |
| `rules` | No rule audit trail |
| `recommendation_rules` | No "why this advice" |
| `sms_messages` | No SMS audit trail |

**Column mismatches in existing tables:**
- `farmers`: missing `alias` (uses `name`), `preferred_language`, `sms_consent`; `phone` is NOT NULL (spec: nullable); no `farmer_id` field
- `readings`: missing `field_id`, `device_id`, `operator_id`, `replicates` (JSON), `quality_status`, `quality_reasons`, `calibration_id`, `ph_water` (renamed); has `prediction`, `confidence`, `advisory`, `nitrogen`, `phosphorus`, `organic_carbon` which don't exist in spec

**Existing data worth migrating:**
The database is 20 KB. Without inspecting the SQLite file directly, it is likely to contain very few test records (the system was built recently). Any farmer records could be migrated by mapping `name` to `alias`, but readings are ML predictions and cannot be converted to the new schema (no replicates, no quality status, no field linkage). **Recommendation: start fresh with a seed script; back up the old DB for reference.**

### Check 4: pH method handling

**No pH method is tracked anywhere.** The current `readings` table has a single `pH` column with no method indicator. The `advisory.py` uses pH for coarse threshold checks (L187–202) but does not distinguish between water and CaCl2. The spec requires `ph_method` on `readings`, `map_estimates`, `lab_results`, and every pH-dependent rule. **This must be built from scratch.**

### Check 5: How readings reach the backend

**Currently:** The dashboard form (`dashboard/index.html` L51–100) collects pH, moisture, temperature (and optional nitrogen, phosphorus, organic_carbon, farmer_phone) and sends them via `POST /predict` (see `dashboard/app.js` L83–99).

**Payload shape:**
```json
{
  "pH": 5.8,
  "moisture": 35.0,
  "temperature": 28.0,
  "farmer_phone": "+260971234567",
  "latitude": null,
  "longitude": null
}
```

The response is a `PredictionResponse` with `soil_health` (ML label), `confidence`, and an `Advisory` object.

**No serial bridge exists.** There is no code for receiving data from an Arduino. The spec expects `POST /readings` from a serial bridge with `device_id`, `field_id`, raw `replicates` (3 values), moisture, and temperature. The current single-value pH input is incompatible with the spec's 3-replicate requirement.

**No manual lab entry path exists either.**

### Check 6: SMS handling

| Aspect | Current state |
|---|---|
| **Sandbox or production** | Sandbox by default (`AT_USERNAME = "sandbox"`). Production if env var `AT_API_KEY` is set. |
| **Where key is read** | `os.environ.get("AT_API_KEY", "")` and `os.environ.get("AT_USERNAME", "sandbox")` in `backend/sms.py` L13–14. **No hardcoded keys.** |
| **Phone storage** | Stored in `farmers.phone` (NOT NULL UNIQUE) and can be passed in `SoilReading.farmer_phone`. No consent field, no deletion mechanism. |
| **Can phones be deleted (NFR5)?** | **No.** There is no DELETE endpoint for farmers or their phone numbers. Phone is required for farmer registration. No consent flag exists. **Violates NFR5.** |

### Check 7: Dashboard mobile readiness

| Aspect | Assessment |
|---|---|
| **Responsive layout** | Yes — CSS uses responsive grid, `max-width: 1200px` container, `@media` queries likely present (the CSS is 1000 lines with a design system). The form grid adapts. |
| **JS bundle size** | `app.js` is 18 KB (small). **But Chart.js 4.4.4 is loaded from CDN** (~200 KB gzipped). On a slow connection this is significant. |
| **Heavy dependencies** | Chart.js is the only external dependency. No React, no framework. |
| **Which pages exist** | Two views: **Farmer view** (submit reading form and prediction result) and **Officer view** (stats cards, health distribution chart, activity chart, farmer directory table, register farmer modal, farmer detail modal with reading history). |
| **Basic phone browser** | Should work — no ES modules, no build step, vanilla JS. But the Chart.js CDN dependency could fail offline. |
| **No login screen** | The dashboard has no auth — anyone can access everything. |
| **No field management** | No field list, no GPS capture, no map view. |

### Check 8: User-facing text in Nyanja or Tonga

**None found.** Zero. All text in the codebase is English only. There are no i18n files, no language selection, no translation keys. The dashboard has no language switch. The SMS messages are English only.

### Check 9: Test coverage

**No tests exist anywhere in the repo.** There are:
- No `test_*.py` or `*_test.py` files
- No `tests/` directory
- No `pytest`, `unittest`, or any testing framework in `requirements.txt`
- No `conftest.py`
- No test configuration in any config file

**Test coverage is 0%.**

### Check 10: Advice from failed quality check

**There is no quality check at all,** so the question is vacuous in one sense — but more seriously, **every reading gets advice regardless of quality.** The current system accepts any pH between 0 and 14 (Pydantic validation in `models.py` L15), runs it through the ML model, and returns advice. There is no concept of:
- Quality failure
- Reading rejection
- "No advice" response

A pH of 0.5 or 13.0 would get a "Critical" prediction and full advice with lime and fertiliser rates. **This violates NFR2** ("never advise from a failed reading") because there is no mechanism to fail a reading at all.

---

## 6. Reuse opportunities

| What to keep | File(s) | Changes needed |
|---|---|---|
| **FastAPI app scaffold** | `backend/main.py` | Remove ML description and `model_loaded` status; add auth middleware; add new routers |
| **Database connection pattern** | `backend/database.py` | Replace inline table creation with migration system; keep `get_connection()` pattern |
| **Farmer CRUD (partial)** | `backend/routes/farmers.py` | Rename `name` to `alias`; make `phone` nullable; add `preferred_language`, `sms_consent`; add delete phone endpoint; reuse CRUD pattern |
| **Farmer Pydantic models (partial)** | `backend/models.py` (`FarmerCreate`, `FarmerResponse`) | Adapt field names; add new fields; remove ML-specific models |
| **SMS integration** | `backend/sms.py` | Add consent check; log to `sms_messages` table; reformat message for plan-based advice; reuse the `send_sms` and credential-handling pattern as-is |
| **Dashboard design system** | `dashboard/style.css` | Keep the entire 1000-line CSS — the dark mode, design tokens, card/form/modal/toast styles are well-built. Add login, field, and advice view styles |
| **Dashboard app shell** | `dashboard/index.html`, `dashboard/app.js` | Keep view switcher, modal system, toast system, form validation pattern, table rendering. Replace reading form and prediction display with spec flows |
| **Raster extraction logic** | `extract_kafue.py` (L120–151) | The CRS transformation and point sampling pattern is correct and reusable for the `MapService`. Adapt from batch to per-field lookup. **Note:** needs iSDAsoil rasters, not SoilGrids |

---

## 7. Data migration notes

**Recommendation: clean start.**

| Data | Migrate? | Rationale |
|---|---|---|
| `farmers` table rows | Maybe | If real farmers were registered, map `name` to `alias`, add `preferred_language: 'en'`, `sms_consent: false`. But if these are test records, start fresh. |
| `readings` table rows | No | ML predictions are meaningless under the new design. No replicates, no quality status, no field linkage. |
| `kafue_soil_data.csv` | No (analysis only) | This is SoilGrids data, not iSDAsoil. Useful for dissertation Chapter 1, not for the product. |
| `soilsense.db` | Back up, then replace | Keep for reference. Create a new DB with migrations. |
| Pickle model files | Delete | `soil_model*.pkl`, `label_encoder*.pkl` |
| Synthetic training data | Delete | `synthetic_training_data*.csv` |
| Plot images | Move to `analysis/` | Dissertation figures, not product files |
| GeoTIFF rasters | Keep for reference | The spec needs iSDAsoil layers (task H6), not SoilGrids. These may still be useful for the dissertation. |

---

## 8. Proposed Sprint 0 and Sprint 1 task list

### Sprint 0 (2–3 days): audit and contract freeze

| # | Task | Done by | Status |
|---|---|---|---|
| S0-1 | Initialise git repo, commit current state | Developer | `done` |
| S0-2 | Copy spec to `docs/SOILSENSE_SPEC.md` (now v0.2; `dissertation/` copy removed) | Developer | `done` |
| S0-3 | Review this migration plan | Developer | `done` |
| S0-4 | Freeze contracts: DB schema (spec S3), API (spec S4), YAML shape (spec S6), i18n key format | Developer | `done` (contracts as built: spec v0.3) |
| S0-5 | Create branches and apply the folder split (spec 8.4) | Developer | `todo` |
| S0-6 | Move analysis scripts to `analysis/` | Antigravity | `done` |

### Sprint 1 — Must

| # | Task | Files touched | Size | Dependencies | Agent | Parallel? | Status |
|---|---|---|---|---|---|---|---|
| **S1-1** | Remove all ML code and dependencies | `train_model.py` (delete), `generate_training_data.py` (delete), `soil_model*.pkl` (delete), `label_encoder*.pkl` (delete), `synthetic_training_data*.csv` (delete), `plots/` (move to `analysis/`), `backend/routes/predict.py` (gut ML parts), `backend/requirements.txt` (remove sklearn/joblib/numpy/pandas), `backend/main.py` (remove ML references), `backend/advisory.py` (delete — will be replaced by rule engine), `backend/models.py` (remove `PredictionResponse`, `Advisory`, `StatusResponse.model_loaded`) | **M** | None | Antigravity (`backend/`) | **Yes** — independent of S1-2 to S1-5 | `done` |
| **S1-2** | Schema and migrations for spec S3 | New: `backend/migrations/`, `backend/schema.py`; Modify: `backend/database.py`; Seed script: `backend/seed.py` | **L** | S1-1 (clean imports) | Antigravity (`backend/`) | After S1-1 | `done` |
| **S1-3** | Field registration with GPS (accuracy, source; reject >30 m; manual pin) | New: `backend/routes/fields.py`, Modify: `backend/routes/farmers.py` (adapt), `dashboard/index.html` (field form), `dashboard/app.js` (GPS capture) | **M** | S1-2 (schema) | Antigravity (`backend/`, `dashboard/`) | After S1-2 | `done` |
| **S1-4** | Firmware, serial bridge, two-buffer calibration | New: `firmware/soilsense.ino`, `bridge/bridge.py`, `backend/routes/devices.py`, `backend/routes/calibrations.py` | **L** | S1-2 (schema for `devices`, `calibrations`), API contract freeze | Claude Code (`firmware/`, `bridge/`) | After S1-2; parallel with S1-3 and S1-5 | `partial` (S1-4b done; S1-4a firmware and bridge on hold for board details) |
| **S1-5** | `QualityChecker` with tests | New: `engine/quality.py`, `tests/test_quality.py` (see 11.3) | **M** | S1-2 (schema for `readings`), S1-4 (reading payload shape) | Claude Code (`engine/`, `tests/`) | After S1-2; can develop in parallel with S1-4 using mocked readings | `done` |

**S1-4 folder note:** The spec assigns Claude Code to `firmware/` and `bridge/`, but S1-4 also requires `backend/routes/devices.py` and `backend/routes/calibrations.py`, which are in `backend/` (Antigravity's territory). **Recommendation:** Split S1-4 into two sub-tasks: S1-4a (firmware + bridge, Claude Code) and S1-4b (backend endpoints for devices and calibrations, Antigravity). They share the API contract but touch different directories.

### Sprint 1 — Should

| # | Task | Files touched | Size | Dependencies | Agent | Parallel? | Status |
|---|---|---|---|---|---|---|---|
| **S1-6** | Dashboard shell: login, language switch, field list, reading screen | `dashboard/index.html`, `dashboard/app.js`, `dashboard/style.css` | **L** | S1-2 (API), S1-3 (fields API) | Antigravity (`dashboard/`) | After S1-3; parallel with S1-4, S1-5 | `done` (UI labels English only; ny/toi advice text in track F) |
| **S1-7** | Rule YAML schema, validator and loader with S6 data | New: `rules/ph_bands.yaml`, `rules/crops.yaml`, `rules/lime.yaml`, `rules/messages.yaml`, `rules/refusals.yaml`, `rules/measures.yaml` (empty stub), `engine/rules.py`, `tests/test_rules.py` (see 11.3) | **L** | API contract freeze (YAML shape) | Claude Code (`engine/`, `rules/`, `tests/`) | **Yes** — independent of S1-1 to S1-6 (different directories) | `done` |

### Dependency graph

```
S1-1 ──→ S1-2 ──→ S1-3 ──→ S1-6
              ├──→ S1-4a (firmware)  ─┐
              ├──→ S1-4b (backend)   ─┤──→ (Sprint 2)
              └──→ S1-5 ─────────────┘
S1-7 (independent, parallel from day 1)
```

---

## 9. Risks

| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| ~~**Not a git repo**~~ | — | Resolved | Repo is on GitHub (`lush-is-him/soilsense-zm`) |
| **advisory.py deletion is a one-way door** — the hardcoded advice is the only working output | High | Certain (must delete per spec) | Back up the file to `analysis/advisory_old.py`; the rule engine replaces it |
| **iSDAsoil rasters not yet obtained** — the spec requires iSDAsoil, the repo has SoilGrids | High | High (task H6 not done) | SoilGrids can be used for development; swap to iSDAsoil before evaluation |
| **No Arduino hardware tested** — firmware is being written without hardware in the repo | High | Unknown | S1-4 must be verified against real hardware |
| **Agronomist follow-up questions unanswered** — C-2, C-3, C-4 and pH method block Plan A and Plan B | High | Medium | Stub with "lab test recommended"; mark `OPEN` in YAML; write xfail tests |
| **Schema redesign with no migration tool** — raw SQL `CREATE TABLE IF NOT EXISTS` | Medium | Certain | Introduce a simple migration system (e.g., `yoyo` or manual numbered SQL files) |
| **Dashboard CDN dependency** — Chart.js loaded from CDN will fail offline | Medium | High (field use) | Bundle locally or replace with a lighter charting solution |
| **Phone numbers stored without consent** — NFR5 violation | Medium | Certain | Add `sms_consent` field and deletion endpoint in S1-2 |

---

## 10. Conflicts and questions

### Conflicts

| Spec conflict | Which code it blocks |
|---|---|
| **C-1** (crop scope: sorghum vs groundnut) | `rules/crops.yaml` — temporary: implement 4 crops, groundnut as `pending`, sorghum as `data: NONE` |
| **C-2** (E7 lime-at-planting numbers) | Plan B — blocked entirely |
| **C-3** (E1 lime trigger pH) | Plan A lime logic — use `trigger_ph: OPEN` |
| **C-4** (pH method for bands and crops) | All pH comparisons — use `ph_method: unconfirmed` + method-sensitivity rule |
| **C-5** (manure unit) | Crop manure display — store tonnes/ha, derive per lima |
| **C-6** (maize lowest workable = best range bottom) | Plan A vs Plan C boundary — treat as "below this, not recommended without liming" |
| **C-7** (lime lead time 2–3 vs 1–2 months) — added v0.2 | REF-05 and Plan A timing — evaluate with both, flag when they differ |
| **C-8** (target pH 5.5–6.5 vs 5.5–7) — added v0.2 | Plan A target and over-liming warning — use 5.5–6.5 |

### Spec problems

- The spec references iSDAsoil layers, but the repo has SoilGrids GeoTIFFs. These are different datasets with different resolutions and units. The spec says the layers need pH mean **and SD**, which iSDAsoil provides but SoilGrids does not (SoilGrids has mean and uncertainty layers with different semantics). Task H6 must be done before the map service can match the spec.
- The spec's data model (S3) puts `ph_water (mean)` in `readings` but the quality checker (S2.3) checks replicates. The reading row should probably store both the raw replicates (JSON) and the computed mean.
- Spec S4 has `POST /readings` for the serial bridge but the end-to-end flow (S2.2 step 2) says "the bridge posts it to the backend" — yet the dashboard can also accept manual readings. The API should clarify whether manual-entry readings go through the same endpoint or a different one.

### Questions for you (most important first)

1. **Is this repository the only copy of the code?** There is no git repo. Should I initialise git and make an initial commit before doing anything else?
2. **Are the farmer records in `soilsense.db` real people or test data?** This decides whether we migrate the `farmers` table or start fresh.
3. **Do you have the Arduino Uno and the pH/moisture/temperature sensors physically?** The spec assumes firmware development, but none exists. Are you writing firmware yourself, or should the agent do it?
4. **Have you downloaded iSDAsoil layers for Kafue yet (task H6)?** The existing rasters are SoilGrids, not iSDAsoil. The map service cannot match the spec without iSDAsoil layers (which include pH SD).
5. **Which migration tool do you prefer?** Options: (a) hand-written numbered SQL files, (b) `yoyo-migrations`, (c) Alembic (heavier, designed for SQLAlchemy). The current code uses raw `sqlite3` with no ORM.
6. **Have you sent the follow-up questions to the agronomist (spec S7.3)?** The answers to C-2 and C-4 block Plan A and Plan B.
7. **Should I keep the SoilGrids GeoTIFFs in the repo or move them to a separate data folder?** They are 1.2 GB and should not be committed to git.
8. **For the dashboard, do you want to keep vanilla HTML/CSS/JS or move to a framework (e.g., Vite + vanilla, or a lightweight framework)?** The current approach works but will get harder to maintain as pages multiply.
9. **The spec assigns some tasks to Claude Code. Are you running Claude Code alongside, or should I handle everything?**
10. **Do you want me to proceed to Phase 2 (Sprint 1 tasks) after you approve this plan?**

---

## 11. Review against spec v0.2 (25 Oct 2026)

This section was added after the audit. It covers what the audit got wrong, what is now out of date, and how the spec v0.2 changes affect the tasks above. Sections 1 to 10 are left as audited, apart from status updates.

### 11.1 Spec changes in v0.2 that affect code

| Change | Affects | What to do |
|---|---|---|
| First reviewer (`AGR-1`, anonymous) will not review scenarios or confirm tables | S1-2 (`rules.reviewer_alias`), S1-7 | Store the alias only, never a name. The validator must reject `status: verified` on a rule whose only support is `AGR-1` expert opinion (no `source_doc` and no second reviewer) |
| **C-7** lime lead time: E5 says 2 to 3 months, E10 says 1 to 2 | REF-05, Plan A timing text (Sprint 3) | `lead_time_before_planting_months: CONFLICT`. The validator must report `CONFLICT` values alongside `OPEN` ones |
| **C-8** target pH: E3 says 5.5 to 6.5, G2 says 5.5 to 7 | Plan A target, over-liming warning | Use 5.5 to 6.5 until resolved |
| REF-05 is evaluated **per crop**, with both 1 and 3 months | REF-05 tests | Scenarios with `as_of_date = 2026-10-25` give "timing uncertain" for maize and sunflower; 15 Dec gives "too late" for maize (rule refined in spec v0.3) |
| C-1: sorghum was never in questionnaire v1 | `rules/crops.yaml` comment only | No behaviour change |
| About 30 new lab samples replace the earlier 12 | Track H (evaluation) only | No Sprint 1 impact |

C-7 and C-8 are also added to the conflict table in section 10.

### 11.2 Corrections to the audit

1. **The second "spec problem" is already covered.** Spec section 3 `readings` holds both `ph_water (mean)` and `replicates (JSON)`. No spec change is needed.
2. **S1-5 does not depend on S1-2 or S1-4.** `QualityChecker` is a pure function (spec 2.1). It takes calibration, replicates, temperature and moisture and returns accepted or rejected with reasons. Its tests can be written on day 1. Only persisting the result needs S1-2.
3. **S1-4a (firmware and bridge) can also start on day 1.** It depends only on the `POST /readings` payload in spec section 4, not on the schema. Only S1-4b (backend endpoints) waits for S1-2.
4. **`soilsense.db` is not in git** (`.gitignore` has `*.db`). Existing farmer records exist only on the developer's laptop, so question 2 applies to that local file.
5. **Chart.js size:** `chart.umd.min.js` is roughly 200 KB minified, about 70 KB gzipped, not 200 KB gzipped. It is still worth removing for low bandwidth and offline use.

Revised dependency graph:

```
S1-1 ──→ S1-2 ──→ S1-3 ──→ S1-6
             └──→ S1-4b (backend endpoints)
S1-4a (firmware + bridge)   independent from day 1
S1-5  (QualityChecker + tests) independent from day 1; wire-up after S1-2
S1-7  (rule YAML + validator)  independent from day 1
```

### 11.3 Folder split: `engine/` (approved)

S1-5 put `backend/quality.py` and S1-7 put `backend/rule_engine.py` in `backend/`, which spec 8.4 assigns to Antigravity, while the tasks go to Claude Code. **Decision:** the pure logic goes in a new folder, `engine/` (`quality.py`, `trust.py`, `rules.py`, `measures.py`), with no FastAPI or database imports. Claude Code edits it; `backend/` imports and wraps it. Spec 8.4 is updated. The split only stops two AI tools editing the same files; all code belongs to the developer.

Revised file paths: S1-5 becomes `engine/quality.py` + `tests/test_quality.py`; S1-7 becomes `engine/rules.py` + `rules/*.yaml` + `tests/test_rules.py`.

### 11.4 Answers to section 10 questions known so far

| # | Answer |
|---|---|
| 1 | Yes, the repo is on GitHub and is the copy of record |
| 6 | Not sent yet. Clarification questions for `AGR-1` are drafted in `docs/QUESTIONS_FOR_REVIEWER_1.md` (questions 1 to 5 block code). `AGR-1` will not review or confirm; a second reviewer is pending |
| 2 | No real farmer data. Start fresh with seed data (S1-2 seed script); the old local `soilsense.db` is not migrated |
| 3 | Yes, all hardware has been bought. **On hold:** the developer will confirm the exact sensor boards before S1-4a starts. pH 4.00 and 7.00 buffers are **not** bought yet (H8); calibration cannot be tested until they are |
| 4 | Not yet downloaded. `scripts/fetch_isdasoil.py` now does it (about 1 minute, about 50 MB); the developer runs it with `--boundary` pointing at the local `gadm41_ZMB.gpkg` |
| 9 | Yes, Claude Code runs alongside Antigravity |
| 5, 7, 8, 10 | Open: developer to answer |

---

## 12. Progress, 26 Oct 2026 (Sprints 1 and 2, done by Claude Code)

Antigravity was offline, so Claude Code did both sprints on branch `engine/sprint2`. The folder split in spec 8.4 still applies when both agents work.

| Area | Status | Where |
|---|---|---|
| S1-1 ML removed | done | analysis scripts and figures moved to `analysis/`; `tests/test_no_ml.py` guards it |
| S1-2 schema, migrations, seed, auth | done | `backend/migrations/001_initial.sql`, `backend/db.py`, `backend/seed.py`, `backend/auth.py` (scrypt + signed tokens, stdlib only). New DB at `data/soilsense.db`; the old `backend/soilsense.db` is untouched |
| S1-3 field registration with GPS | done | `POST /fields` rejects fixes worse than 30 m; manual pins stored as `manual`; dashboard uses the phone's GPS |
| S1-4a firmware and serial bridge | **on hold** | needs the exact sensor boards; buffers not bought yet |
| S1-4b calibrations and readings API | done | `backend/routes/devices.py`, `readings.py`; electrode mV in, slope 95-105% |
| S1-5 quality checker | done | `engine/quality.py`, `tests/test_quality.py` |
| S1-6 dashboard shell | done | `dashboard/`: login, fields, GPS, probe calibration, readings, field checks, lab results, advice, sampling help; no external libraries |
| S1-7 rule YAML and validator | done | `rules/*.yaml`, `python -m engine.validate` |
| Sprint 2: map service | done | `engine/map_service.py`, `GET /fields/{id}/map-estimate` (needs `scripts/fetch_isdasoil.py` run once) |
| Sprint 2: trust checker | done | `engine/trust.py` |
| Sprint 2: field checks | done | `POST /fields/{id}/checks`, dashboard form |
| Sprint 2: rule engine Plans A and C | done | `engine/advice.py`; Plan B returns the blocked message |
| Sprint 2: scenario harness | done | `scripts/run_scenarios.py` writes `docs/scenarios/scenarios.csv` (96 synthetic scenarios, blank reviewer columns) |
| Not built | — | `PATCH /rules` (rules are edited in YAML), household measures (H3), Nyanja and Tonga text (track F), real SMS (needs an Africa's Talking key) |

Tests: `python -m pytest`: 105 passing, 7 expected failures, each naming an OPEN or CONFLICT item.

### Findings while building

1. **The pH method question blocks most advice.** With `ph_method: unconfirmed`, 87 of the 96 scenarios give different advice under water and CaCl2 readings, so the engine returns "lab test recommended" instead of quantities. Question 1 to AGR-1 (water or CaCl2?) is the most valuable answer to get.
2. **The iSDAsoil map says Kafue is less acidic than the agronomist expects.** District mean pH 6.15 (water), none below 5.5, about a quarter below 6.0. AGR-1 expects 4.5 to 5.5 (C3). That fits his numbers being CaCl2. The 30 lab samples (water and CaCl2) will show which.
3. **The map's pH SD is small** (median 0.1, max 1.0, stored in steps of 0.1), so the agreement threshold T = 0.5 + SD is set almost entirely by `E_PROBE`. RQ1 matters for the trust design.
4. **The borderline flag is meaningless as specified** (C-9).
5. **Texture grouping is an engineering proposal** (`rules/texture.yaml`): USDA classes are mapped to sandy, loamy and clay for the lime table. It changes lime rates by up to 2 times and needs a reviewer.
6. **REF-05 refined** (spec v0.3): on 25 Oct, maize and sunflower give "timing uncertain", not "too late".

---

*End of Phase 1 audit. Waiting for your review before making any code changes.*
