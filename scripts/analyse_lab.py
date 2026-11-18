"""What the laboratory results and the AGR-3 review show (Ch 5).

    python scripts/analyse_lab.py --map-dir data/isdasoil [--out docs/evaluation/lab_analysis.md]

Reads docs/evaluation/samples.csv (ZARI Soil Chemistry Laboratory, 18 Nov 2026: pH in
0.01 M CaCl2 at 1:2.5) and answers, with leave-one-out checks because the samples are few:

1. Probe and pen meter against the lab, and whether one constant offset learned from the
   lab corrects the probe (the "lab anchor").
2. The iSDAsoil map against the lab, for pH and nutrients.
3. Whether pH predicts the other nutrients at this site (can pH alone drive the advice?).
4. Whether the advice from the probe, the corrected probe and the lab would be the same.
5. Patterns in the AGR-3 review: what the disagreements are about, and AGR-3's lime rates.

Pure Python: no numpy or scipy, so it runs wherever the system runs.
"""

import argparse
import csv
import itertools
import math
import random
import statistics as st
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.advice import AdviceRequest, Advisor  # noqa: E402
from engine.config import DEFAULT_CONFIG  # noqa: E402
from engine.ruleset import load  # noqa: E402

CROPS = ("maize", "soybean", "sunflower", "millet", "groundnut")
W_MINUS_C = DEFAULT_CONFIG.PH_WATER_MINUS_CACL2            # (0.5, 0.8)
W_MID = round(sum(W_MINUS_C) / 2, 2)                       # 0.65

# AGR-3's own lime advice in the review form (situations where she named a rate).
# (situation, scenario id, pH in water, crop, t/ha)
AGR3_LIME = [
    (1, "S001", 4.2, "maize", 4.0),
    (2, "S007", 4.5, "soybean", 3.5),
    (3, "S013", 4.9, "sunflower", 2.5),
    (4, "S014", 4.9, "millet", 2.0),
    (5, "S020", 5.2, "groundnut", 2.0),
    (6, "S021", 5.5, "maize", 1.0),
]


def num(v):
    v = (v or "").strip()
    return float(v) if v else None


def pearson(x, y):
    return st.correlation(x, y) if len(x) > 2 else float("nan")


def ranks(v):
    order = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def spearman(x, y):
    return pearson(ranks(x), ranks(y))


def perm_p(x, y, n=20000, seed=1):
    """Two-sided permutation p-value for Spearman's rho."""
    rho = abs(spearman(x, y))
    rng = random.Random(seed)
    ry, rx = ranks(y), ranks(x)
    y2 = list(ry)
    hits = 0
    for _ in range(n):
        rng.shuffle(y2)
        if abs(pearson(rx, y2)) >= rho - 1e-12:
            hits += 1
    return (hits + 1) / (n + 1)


def errors(pairs):
    d = [e - r for e, r in pairs]
    a = [abs(x) for x in d]
    return {"n": len(d), "bias": st.mean(d), "mae": st.mean(a), "rmse": math.sqrt(st.mean([x * x for x in d])),
            "max": max(a), "w03": sum(x <= 0.3 for x in a), "w05": sum(x <= 0.5 for x in a)}


def fmt_err(e):
    return (f"bias {e['bias']:+.2f}, MAE {e['mae']:.2f}, RMSE {e['rmse']:.2f}, largest {e['max']:.2f}, "
            f"within 0.3: {e['w03']}/{e['n']}, within 0.5: {e['w05']}/{e['n']}")


def loo_offset(est, ref):
    """Leave-one-out: correct each sample with the mean offset of the others."""
    out = []
    for i in range(len(est)):
        others = [est[j] - ref[j] for j in range(len(est)) if j != i]
        out.append(est[i] - st.mean(others))
    return out


def loo_linear(x, y):
    out = []
    for i in range(len(x)):
        xs = [x[j] for j in range(len(x)) if j != i]
        ys = [y[j] for j in range(len(x)) if j != i]
        b = st.covariance(xs, ys) / st.variance(xs)
        a = st.mean(ys) - b * st.mean(xs)
        out.append(a + b * x[i])
    return out


def loo_r2(x, y):
    """Predictive R^2 of y from x, leave-one-out (<= 0 means no better than the mean)."""
    pred = loo_linear(x, y)
    mean_pred = [st.mean([y[j] for j in range(len(y)) if j != i]) for i in range(len(y))]
    sse = sum((p - t) ** 2 for p, t in zip(pred, y))
    sst = sum((m - t) ** 2 for m, t in zip(mean_pred, y))
    return 1 - sse / sst


def offset_with_k_pairs(est, ref, k):
    """Mean error on the held-out samples when the offset comes from k lab pairs (all subsets)."""
    errs = []
    idx = range(len(est))
    for subset in itertools.combinations(idx, k):
        off = st.mean([est[i] - ref[i] for i in subset])
        errs += [abs(est[i] - off - ref[i]) for i in idx if i not in subset]
    return st.mean(errs), max(errs)


def plan_a(advisor, ph, method, crop):
    r = advisor.advise(AdviceRequest(ph=ph, ph_method=method, trust_level="high", crop=crop,
                                     as_of_date=date(2026, 11, 1), texture="loamy", texture_source="field_check"))
    pa = r.get("plan_a") or {}
    if r.get("refusals") and not pa:
        return "refused"
    lime = (pa.get("lime") or {}) if isinstance(pa.get("lime"), dict) else {}
    return f"{pa.get('status')}/{lime.get('status') or pa.get('lime_status') or '-'}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", default=ROOT / "docs" / "evaluation" / "samples.csv")
    ap.add_argument("--map-dir", default=None)
    ap.add_argument("--review", default=None, help="AGR-3 form responses CSV (kept out of the repository)")
    ap.add_argument("--out", default=ROOT / "docs" / "evaluation" / "lab_analysis.md")
    args = ap.parse_args()

    rows = [r for r in csv.DictReader(open(args.samples, encoding="utf-8")) if num(r.get("lab_ph_cacl2")) is not None]
    for r in rows:
        reps = [num(r.get(f"probe_ph_{i}")) for i in (1, 2, 3)]
        reps = [x for x in reps if x is not None]
        r["probe"] = round(st.mean(reps), 2) if reps else None
        r["meter"] = num(r.get("meter_ph"))
        r["lab"] = num(r["lab_ph_cacl2"])

    out = ["# Laboratory results and review: analysis", "",
           "Generated by `scripts/analyse_lab.py`. Laboratory: ZARI Soil Chemistry Laboratory, 18 Nov 2026, "
           f"{len(rows)} samples, pH in 0.01 M CaCl2 at 1:2.5. The probe and pen meter measure pH in water, which reads "
           f"higher than CaCl2; the rules assume a difference of {W_MINUS_C[0]} to {W_MINUS_C[1]} (midpoint {W_MID}).", ""]

    # ---- 1. probe and meter
    paired = [r for r in rows if r["probe"] is not None]
    ids = [r["sample_id"] for r in paired]
    probe = [r["probe"] for r in paired]
    meter = [r["meter"] for r in paired]
    lab = [r["lab"] for r in paired]
    out += ["## 1. Probe and pen meter against the laboratory", "",
            f"Samples measured with both field instruments: {len(paired)} ({', '.join(ids)}).", "",
            "| Comparison | Result |", "|---|---|",
            f"| Probe (water) − lab (CaCl2) | {fmt_err(errors(list(zip(probe, lab))))} |",
            f"| Pen meter (water) − lab (CaCl2) | {fmt_err(errors(list(zip(meter, lab))))} |",
            f"| Probe − lab converted to water (+{W_MID}) | {fmt_err(errors([(p, l + W_MID) for p, l in zip(probe, lab)]))} |",
            f"| Pen meter − lab converted to water (+{W_MID}) | {fmt_err(errors([(m, l + W_MID) for m, l in zip(meter, lab)]))} |",
            f"| Correlation with the lab (Pearson r) | probe {pearson(probe, lab):.2f}, pen meter {pearson(meter, lab):.2f} |",
            f"| Correlation with the lab (Spearman ρ) | probe {spearman(probe, lab):.2f}, pen meter {spearman(meter, lab):.2f} |", ""]
    diffs = [p - l for p, l in zip(probe, lab)]
    out += [f"Probe minus lab, sample by sample: " + ", ".join(f"{i} {d:+.2f}" for i, d in zip(ids, diffs)) +
            f" (spread: SD {st.stdev(diffs):.2f}).", ""]

    loo = loo_offset(probe, lab)
    lin = loo_linear(probe, lab)
    out += ["### The lab anchor: correcting the probe with one constant offset", "",
            "The probe's error is nearly the same at every sample, so it can be removed with one offset learned from "
            "samples that also went to the laboratory. To avoid judging the offset on the samples it was learned from, "
            "each sample is corrected with the offset of the *other* samples (leave-one-out).", "",
            "| Correction | Error against the lab (CaCl2 scale), held-out samples |", "|---|---|",
            f"| None | {fmt_err(errors(list(zip(probe, lab))))} |",
            f"| Fixed rule offset (−{W_MID}, water to CaCl2) | {fmt_err(errors([(p - W_MID, l) for p, l in zip(probe, lab)]))} |",
            f"| Lab anchor: constant offset, leave-one-out | {fmt_err(errors(list(zip(loo, lab))))} |",
            f"| Straight line (slope and offset), leave-one-out | {fmt_err(errors(list(zip(lin, lab))))} |", ""]
    out += ["How many lab samples does the anchor need? Mean and largest error on the remaining samples, over every "
            "possible choice of k anchor samples:", "", "| Lab samples used (k) | Mean error | Largest error |", "|---|---|---|"]
    for k in (1, 2, 3, 4):
        m, mx = offset_with_k_pairs(probe, lab, k)
        out.append(f"| {k} | {m:.2f} | {mx:.2f} |")
    out.append("")

    # ---- 2. map
    if args.map_dir:
        from engine.map_service import MapService
        svc = MapService(Path(args.map_dir))
        for r in rows:
            r["map"] = svc.lookup(float(r["lat"]), float(r["lon"]))
        m_ph = [r["map"].ph_mean for r in rows]
        l_ph = [r["lab"] for r in rows]
        out += ["## 2. The iSDAsoil map against the laboratory", "",
                f"All {len(rows)} samples lie in about 370 × 170 m. Lab pH (CaCl2) ranges {min(l_ph):.2f}–{max(l_ph):.2f}; "
                f"the map gives {min(m_ph):.1f}–{max(m_ph):.1f} (water).", "",
                "| Property | Map vs lab | Pearson r | Bias (map − lab) | MAE |", "|---|---|---|---|---|"]
        e = errors([(m, l + W_MID) for m, l in zip(m_ph, l_ph)])
        out.append(f"| pH | map (water) vs lab + {W_MID} | {pearson(m_ph, l_ph):.2f} | {e['bias']:+.2f} | {e['mae']:.2f} |")
        e = errors(list(zip(m_ph, l_ph)))
        out.append(f"| pH | map (water) vs lab as reported (CaCl2) | {pearson(m_ph, l_ph):.2f} | {e['bias']:+.2f} | {e['mae']:.2f} |")
        for label, mk, lk, scale in (("Organic carbon (g/kg)", "oc_g_kg", "lab_oc_pct", 10.0),
                                     ("P (map mg/kg, lab mg/L)", "p_ppm", "lab_p_mg_kg", 1.0),
                                     ("K (map mg/kg, lab mg/L)", "k_ppm", "lab_k_cmol_kg", 391.0)):
            pairs = [(getattr(r["map"], mk), num(r[lk]) * scale) for r in rows if getattr(r["map"], mk) is not None]
            mv, lv = [p[0] for p in pairs], [p[1] for p in pairs]
            e = errors(pairs)
            out.append(f"| {label} | {len(pairs)} samples | {pearson(mv, lv):.2f} | {e['bias']:+.1f} | {e['mae']:.1f} |")
        out.append("")

    # ---- 3. does pH predict the nutrients?
    names = [("P (mg/L)", "lab_p_mg_kg", 1), ("K (mg/L)", "lab_k_cmol_kg", 391.0), ("Ca (mg/L)", "lab_ca_mg_l", 1),
             ("Mg (mg/L)", "lab_mg_mg_l", 1), ("N (%)", "lab_n_pct", 1), ("Organic carbon (%)", "lab_oc_pct", 1),
             ("CEC (cmol+/kg)", "lab_cec_cmol_kg", 1), ("Cu (mg/L)", "lab_cu_mg_l", 1), ("Mn (mg/L)", "lab_mn_mg_l", 1),
             ("Fe (mg/L)", "lab_fe_mg_l", 1), ("Zn (mg/L)", "lab_zn_mg_l", 1)]
    l_ph = [r["lab"] for r in rows]
    out += ["## 3. Does pH tell us the nutrients?", "",
            "Lab pH against each nutrient, all 20 samples. ρ is Spearman's rank correlation, p a two-sided permutation "
            "test (20,000 shuffles), and R²(LOO) how well a straight line from pH predicts a sample it was not fitted "
            "on (0 or below means no better than guessing the average).", "",
            "| Nutrient | Range | Median | ρ with pH | p | R²(LOO) |", "|---|---|---|---|---|---|"]
    for label, key, scale in names:
        v = [num(r[key]) * scale for r in rows]
        out.append(f"| {label} | {min(v):.3g}–{max(v):.3g} | {st.median(v):.3g} | {spearman(l_ph, v):+.2f} | "
                   f"{perm_p(l_ph, v):.3f} | {loo_r2(l_ph, v):+.2f} |")
    p = [num(r["lab_p_mg_kg"]) for r in rows]
    out += ["", f"Phosphorus: {sum(x <= 3 for x in p)} of {len(p)} samples at 3 mg/L or less, highest {max(p):.0f}; "
            f"median at pH below 6.5: {st.median([x for x, h in zip(p, l_ph) if h < 6.5]):.0f}, "
            f"at 6.5 and above: {st.median([x for x, h in zip(p, l_ph) if h >= 6.5]):.0f}.", ""]
    cec = [num(r["lab_cec_cmol_kg"]) for r in rows]
    ca = [num(r["lab_ca_mg_l"]) for r in rows]
    out += [f"Calcium and CEC between themselves: Spearman ρ {spearman(ca, cec):+.2f}.", ""]

    # ---- 4. would the advice be the same?
    adv = Advisor(load(ROOT / "rules"))
    anchored = loo
    same_raw = same_anchor = total = 0
    diffs_raw = []
    for i, sid in enumerate(ids):
        for crop in CROPS:
            ref = plan_a(adv, lab[i], "cacl2", crop)
            a = plan_a(adv, probe[i], "water", crop)
            b = plan_a(adv, round(anchored[i] + W_MID, 2), "water", crop)
            total += 1
            same_raw += a == ref
            same_anchor += b == ref
            if a != ref:
                diffs_raw.append(f"{sid} {crop}: probe {a}, lab {ref}")
    out += ["## 4. Would the advice be the same?", "",
            "Plan A (status/lime) for the five crops at the eight samples, from the lab pH (entered as CaCl2, which the "
            "engine converts), the probe as measured, and the probe corrected by the lab anchor (leave-one-out).", "",
            f"- Probe as measured: same Plan A as the lab in **{same_raw} of {total}** cases.",
            f"- Probe with the lab anchor: same Plan A as the lab in **{same_anchor} of {total}** cases.", ""]
    limits = sorted({v for c in CROPS for v in (adv.rules.crop(c).data["ph"]["lowest_workable"],
                                               adv.rules.crop(c).data["ph"]["highest_workable"])})
    near = [sid for sid, l in zip(ids, lab) if any(abs(l + W_MID - v) <= 0.15 for v in limits)]
    out += [f"Converted to water, {len(near)} of {len(ids)} lab values ({', '.join(near) or 'none'}) lie within 0.15 of a "
            f"crop's pH limit ({', '.join(f'{v:g}' for v in limits)}), less than the uncertainty of the conversion "
            f"itself ({W_MINUS_C[0]}–{W_MINUS_C[1]}); there any method can flip the decision, so the error in pH "
            "(section 1) is the fairer measure of the probe.", ""]
    if diffs_raw:
        out += ["Differences with the uncorrected probe: " + "; ".join(diffs_raw[:12]) + ("; …" if len(diffs_raw) > 12 else ""), ""]

    # ---- 5. review
    out += ["## 5. The AGR-3 review", ""]
    if args.review:
        r = next(csv.DictReader(open(args.review, encoding="utf-8")))
        keys = __import__("json").load(open(ROOT / "docs" / "scenarios" / "review_keys.json"))
        scen = {s["id"]: s for s in csv.DictReader(open(ROOT / "docs" / "scenarios" / "scenarios.csv", encoding="utf-8"))}
        score = {"agree": 1.0, "partly": 0.5, "disagree": 0.0}
        by_season, season_comment = {"before": [], "in": []}, 0
        for n in range(1, 31):
            ans = r[f"R{n}. Situation {n}: do you agree?"].strip().lower()
            com = r[f"C{n}. Situation {n}: if not Agree, what is wrong?"].lower()
            sc = scen[keys[str(n)]]
            when = date.fromisoformat(sc["when"])
            key = "before" if (sc["water"] == "rainfed" and (when.month, when.day) < (10, 20)) else "in"
            by_season[key].append(score[ans])
            season_comment += ans != "agree" and "season" in com
        allv = by_season["before"] + by_season["in"]
        out += [f"- Overall agreement: **{100 * st.mean(allv):.0f}%** of 30 (Partly counts half).",
                f"- Rain-fed situations dated before the planting season (1 August): {100 * st.mean(by_season['before']):.0f}% "
                f"of {len(by_season['before'])}.",
                f"- Situations in or after the season, or irrigated: {100 * st.mean(by_season['in']):.0f}% of {len(by_season['in'])}.",
                f"- Not full agreement and the comment names the planting season: {season_comment} of "
                f"{sum(v < 1 for v in allv)}.", ""]
    x = [s[2] for s in AGR3_LIME]
    y = [s[4] for s in AGR3_LIME]
    b = st.covariance(x, y) / st.variance(x)
    a = st.mean(y) - b * st.mean(x)
    out += ["AGR-3's own lime rates (loamy soil, situations where a rate was named) against the rule table:", "",
            "| Situation | pH | Crop | AGR-3 (t/ha) | Rule table, loam (t/ha) |", "|---|---|---|---|---|"]
    for n, sid, ph, crop, t in AGR3_LIME:
        rate = (adv.advise(AdviceRequest(ph=ph, ph_method="water", trust_level="high", crop=crop, as_of_date=date(2026, 8, 1),
                                         texture="loamy", texture_source="field_check")).get("plan_a") or {}).get("lime") or {}
        rr = rate.get("rate_t_ha")
        out.append(f"| {n} | {ph} | {crop} | {t} | {'–'.join(f'{v:g}' for v in rr) if rr else '0'} |")
    out += ["", f"AGR-3's rates fall by about **{-b:.1f} t/ha per pH unit** (straight line: {a:.1f} − {-b:.1f} × pH, "
            f"r = {pearson(x, y):.2f}).", ""]

    Path(args.out).write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
