# Probe vs pen pH meter (interim check, 5 Nov 2026)

Before the lab results arrive, the retained samples were measured with the SoilSense probe
(PH-4502C, calibrated 5 Nov, slope 103.7 %) and with a handheld pen pH meter, in the soil-water mix
(10 ml soil, 30 ml water). 8 of the 20 retained samples were measured; the
rest were stored at another location and not recovered in time. Sample S06 was saved under S09 by
mistake and moved with `python scripts/move_sample.py S09 S06`.

| Sample | Pen meter pH | Probe pH | Probe − meter |
|---|---|---|---|
| S01 | 8.06 | 8.55 | +0.49 |
| S02 | 7.78 | 7.73 | −0.05 |
| S04 | 6.91 | 6.91 | 0.00 |
| S05 | 6.94 | 7.59 | +0.65 |
| S06 | 7.90 | 8.83 | +0.93 |
| S08 | 7.46 | 7.49 | +0.03 |
| S10 | 7.20 | 7.62 | +0.42 |
| S16 | 8.02 | 8.16 | +0.14 |

- Mean difference (bias): **+0.33** (the probe reads higher than the pen meter)
- Mean absolute difference: **0.34**; RMSE 0.46
- Within ±0.3: **4 of 8**; within ±0.5: **6 of 8**
- Correlation: **r = 0.82**

## How to read this

- The pen meter is not a reference method. Its own calibration on the day is not recorded, so
  this shows agreement between two field instruments, not the accuracy of either. RQ1 is answered
  against the laboratory results (`scripts/evaluate.py`).
- All samples are neutral to alkaline (pH 6.9–8.8). That is plausible for the area: limestone is quarried
  around Shimabala (confirm with a geological source before citing it). The iSDAsoil map (about pH 6.2 at these points) underestimates it, which is why the system
  gives *low* confidence ("probe and map disagree") instead of trusting the map.
- The largest gaps (S06, S05, S01) are all in the higher readings. Possible causes: the probe was
  calibrated with pH 4 and 7 buffers only, so readings above 7 are an extrapolation; the soil
  settling in the cup; or the time each instrument was left to stabilise. A pH 10 buffer would test
  the first.
