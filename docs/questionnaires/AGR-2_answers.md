# Second agronomist (AGR-2): answers and what they changed

Form returned 1 Nov 2026. Anonymised at the reviewer's request ("role only"): diploma in crop science, research assistant technician at a seed company, 2 years of smallholder agronomy experience in Zambia, with experience in Lusaka Province or Kafue District. The raw response sheet is kept off the repository.

**Independence:** AGR-2 answered **Yes** to "Are you related to the student?". The dissertation must say so wherever it describes the review (Ch 1 limitations, Ch 3 data collection and RQ3), and rules confirmed only by AGR-2 should be described as confirmed by a related reviewer.

## Answers applied to the rule tables

| Item | Answer | Rule changed | Effect |
|---|---|---|---|
| pH method (C-4) | pH in water | BAND-01, crops, LIME-*, REF-02/04, PLAN-C-ORDER: `ph_method: water` | Advice is no longer method-sensitive for probe and map readings (87 of 96 scenarios now give amounts) |
| Lime trigger, maize (C-3) | Below pH 5.5 | LIME-TRIGGER `trigger_ph: 5.5` | Matches what the engine already did |
| Target pH (C-8) | 5.5 to 6 | LIME-TARGET `[5.5, 6.0]` | The range all answers share |
| Refuse below (C5) | pH 4.5 | REF-02 verified | No change in behaviour |
| Shortest lead time (C-7) | 3 months | LIME-LEAD-TIME `[2, 3]` | AGR-1 E5 (2-3) and AGR-2 agree; E10 (1-2) dropped |
| Partial budget order (I2) | Seed, fertiliser, lime, manure | PLAN-B `priority_order` | Plan B now shows the items in this order |
| Lime at planting station (C-2) | Yes, 15 g per station at 75 x 25 cm, source "Conservation Farming Unit" | LIME-PARTIAL per station 15 g | About 0.8 t/ha, 200 kg per lima |
| Lima | 0.25 ha | MEAS-LIMA verified | No change |
| Sampling depth | 20 cm | none (spec already 0-20 cm) | Confirms the map layer choice |
| Crop values (maize, soybean, sunflower, millet, groundnut) | Agree with all | crop rules: reviewer AGR-2 | First reviewer's values confirmed |
| Fertiliser rates | maize basal 200-350, top 150-350; soybean basal 150-200; sunflower basal 150-200 (Compound D), top 100-150 (urea); millet basal 150 (Compound D), top 100-150 (urea); groundnut basal 200 (Compound D), top 200-400 gypsum (kg/ha) | crop rules | Plan A shows fertiliser amounts per lima |
| Lime rate table | Agree ("international lime standards") | LIME-RATES verified | |
| Groundnut in the system? | Yes | not changed (C-1 is the supervisor's decision) | |
| Sources | Zambia Soil Health Consortium; ZARI | notes only | No document titles given |
| Scenario review (RQ3) | Maybe, fewer scenarios; spreadsheet on a computer; next month | — | Send a shorter sheet (about 30 scenarios) |

## Answers that need a follow-up question

1. **Maximum lime in one application:** answered "100000", which cannot be tonnes per hectare. Ask again; 5 t/ha (AGR-1) is kept.
2. **Lime trigger for other crops:** "5.1 to 6.1". Ask: does it mean lime below 5.1 for some crops and below 6.1 for others? Which crops?
3. **Texture grouping:** marked "Agree" but the corrections list clay loam under both loamy and clay, and leave out loam, sandy loam, sandy clay loam, clay, silty clay and sandy clay. Ask him to place each of the 12 classes once.
4. **Soybean top dressing rate:** not given.
5. **How far each budget band reaches in Plan B:** not asked. Until answered, Plan B lists all items in his order and says to stop where the money ends.
6. **Groundnut best pH 5.8-6.0:** he agreed with it, but the range is unusually narrow; worth one more check.

## Follow-up answers (form, 10 Nov 2026)

| Code | Question | Answer | Applied in |
|---|---|---|---|
| T1–T12 | Texture class → group | Sand: not sure (kept sandy); Loamy sand: sandy; Sandy loam, Loam, Sandy clay loam, Clay loam, Sandy clay: loamy; Silt loam, Silt, Silty clay loam, Silty clay, Clay: clay | `rules/texture.yaml` TEX-GROUPS |
| N1 | Maximum lime in one application | blank | LIME-MAX stays at AGR-1's 5 t/ha |
| N2–N5 | Lime below pH: soybean, sunflower, millet, groundnut | 5.5, 5.5, 5.0, 5.8 | `rules/lime.yaml` LIME-TRIGGER `other_crops` |
| N6 | Soybean top dressing | None | `rules/crops.yaml` CROP-SOYBEAN |
| N7 | Groundnut best pH range | 6.2 to 6.5 | `rules/crops.yaml` CROP-GROUNDNUT |
| B1–B2 | Plan B reach: low / medium budget | the first 2 / the first 3 | `rules/plans.yaml` PLAN-B `items_by_budget` |

The raw response sheet is kept out of the repository.
