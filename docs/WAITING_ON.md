# What is left, and what each item plugs into

All code is in place. What remains depends on people, hardware or results outside the developer's control. When one arrives, this page says exactly where it goes. No new code is needed for any of them.

| # | Waiting on | Who | When it arrives | Then run |
|---|---|---|---|---|
| 1 | **pH method** of the bands and crop table (water or CaCl2), question 1 | Agronomist (AGR-1) | Set `ph_method:` of BAND-01 in `rules/ph_bands.yaml` to `water` or `cacl2` (the engine reads it for all pH rules), and change the other `ph_method: unconfirmed` entries to match for the record | `python -m pytest` (the C-4 xfail turns into a pass: remove its marker) |
| 2 | Partial lime rate (C-2, question 2) and priority order (I2, question 5) | Agronomist | `rules/lime.yaml` LIME-PARTIAL: `{method: per_station, g_per_station: [a, b]}` or `{method: per_hectare, kg_ha: [a, b]}`; `rules/plans.yaml` PLAN-B: `priority_order` and `items_by_budget` | Plan B appears automatically |
| 3 | Lime trigger (C-3), lead time (C-7), target (C-8), max (E6), top-dress and basal rates, refusal pH (C5), groundnut range, sorghum | Agronomist | The `OPEN` / `CONFLICT` value named in each rule; `python -m engine.validate` lists them all | `python -m engine.validate`, `python -m pytest` |
| 4 | A second reviewer who confirms the tables | Second agronomist | Change `status:` to `verified` and `reviewer_alias:` to their alias (e.g. `AGR-2`) on each rule they confirm | `python -m engine.validate` (refuses `verified` without a confirming reviewer or a published source) |
| 5 | Scenario review for RQ3 | Second agronomist | They fill `agronomist_*` columns in `docs/scenarios/scenarios.csv` (regenerate it first with `python scripts/run_scenarios.py` once rules change) | `python scripts/score_review.py` |
| 6 | Lab results for the 30 samples (pH water and CaCl2; OC, P, K, texture if affordable) | Lab (UNZA or ZARI) | `docs/evaluation/samples.csv` (with your probe readings of the retained bags) | `python scripts/evaluate.py` → `docs/evaluation/results.md` (RQ1, RQ2, measured water–CaCl2 gap). Then set `E_PROBE` (environment variable) to the largest error and `PH_WATER_MINUS_CACL2` in `engine/config.py` to the measured range |
| 7 | pH 4.00 and 7.00 buffers, distilled water | You (buy) | — | `python -m bridge.bridge calibrate ...` (see `firmware/README.md`) |
| 8 | Exact pH board model and its volts per pH | You (check the board) | `bridge/boards.py`: correct `gain`, set `confirmed: True` | `python -m bridge.bridge calibrate ...` should give 95–105 % |
| 9 | Moisture sensor dry/wet values | You (`python -m bridge.bridge moisture`) | Send the two numbers; they set the waterlogging threshold (spec 2.3, OPEN) | — |
| 10 | Household container weights (H3) | You (weigh) | `rules/measures.yaml`: kg per container per material | Advice shows buckets, bags, tins automatically |
| 11 | Prices with place and date (H4, optional) | You | `rules/prices.yaml`: `zmw_per_kg` | Advice shows cost ranges automatically |
| 12 | Native Nyanja and Tonga reviewers (H5) | Reviewers | `python scripts/i18n_sheet.py export`, they fill `docs/translations/review_sheet.csv` | `python scripts/i18n_sheet.py import` |
| 13 | Usability sessions | Farmers and operators | `docs/evaluation/sus.csv` (form: `docs/evaluation/sus_form.md`) | `python scripts/sus.py` |
| 14 | Africa's Talking key (optional, SMS demo) | You | `AT_API_KEY`, `AT_USERNAME` environment variables | Send SMS from the advice screen |
| 15 | Crop scope decision (C-1: sorghum, groundnut) | Supervisor | `in_scope:` in `rules/crops.yaml` | — |

## For field use

Phone browsers only give GPS to pages served over HTTPS (or localhost). For field tests from a phone, serve the laptop over HTTPS, for example with a tunnel service, or register fields with a manual pin.
