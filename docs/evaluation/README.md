# Evaluation kit (spec 9 and 10; RQ1 to RQ3 and usability)

Everything here turns results you are waiting for into dissertation numbers with one command.

| You receive | Put it in | Run | You get |
|---|---|---|---|
| Lab results for the 20 samples, plus your probe readings of the retained bags | `docs/evaluation/samples.csv` | `python scripts/evaluate.py` | `docs/evaluation/results.md`: RQ1 probe error, measured water-CaCl2 gap, RQ2 map vs lab |
| The reviewer's filled-in scenario sheet | `docs/scenarios/scenarios.csv` (columns `agronomist_*`) | `python scripts/score_review.py` | RQ3 agreement % and the list of disagreements |
| SUS forms from usability sessions | `docs/evaluation/sus.csv` | `python scripts/sus.py` | SUS scores, mean and spread |

## Filling in `samples.csv`

One row per composite sample (S01 to S20 are pre-filled; add rows if you send more).

| Column | What to write |
|---|---|
| `lat`, `lon`, `gps_accuracy_m` | Phone GPS **at the sampling spot, at the time of sampling** (decimal degrees, e.g. -15.7712, 28.1834) |
| `depth_cm` | e.g. `0-20` |
| `probe_ph_1..3`, `probe_temp_c` | Your probe on the **retained bag**: 1:2.5 soil:water, three readings |
| `lab_ph_water`, `lab_ph_cacl2` | As on the lab report (1:2.5) |
| `lab_oc_pct` | Organic carbon in **%** (the script converts to g/kg to compare with the map) |
| `lab_p_mg_kg`, `lab_p_method` | Available P in mg/kg (= ppm) and the method name on the report (Bray-1, Mehlich-3, Olsen...) |
| `lab_k_cmol_kg` | Exchangeable K in **cmol(+)/kg** (the script converts: 1 cmol/kg = 391 mg/kg). If the lab gives mg/kg, divide by 391 first |
| `lab_texture` | USDA class as written by the lab (e.g. Sandy Clay Loam) |

Leave a cell empty if the lab did not measure it. The script reports how many samples each result is based on.

Note: iSDAsoil P and K are modelled Mehlich-3 extractable values. If your lab uses another P method, the P comparison is indicative only; the report says so.
