"""Probe and map against the lab (RQ1, RQ2) from docs/evaluation/samples.csv.

    python scripts/evaluate.py
    python scripts/evaluate.py --samples my.csv --out results.md --map-dir data/isdasoil

Writes a Markdown report and a per-sample CSV next to it. Samples with an
empty cell are left out of the calculations that need that cell, and the
report states how many samples each figure rests on.
"""

import argparse
import csv
import math
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.config import DEFAULT_CONFIG  # noqa: E402

K_CMOL_TO_MG = 391.0          # 1 cmol(+)/kg K = 39.1 g/mol * 10 mg
REPLICATE_SPREAD_MAX = DEFAULT_CONFIG.REPLICATE_SPREAD_MAX
RQ1_TARGET_MAE = 0.5          # Ch 1 provisional target


def num(row, key):
    value = (row.get(key) or "").strip()
    try:
        return float(value) if value else None
    except ValueError:
        raise SystemExit(f"{row.get('sample_id')}: '{key}' is not a number: {value!r}")


def errors_summary(pairs):
    """pairs: list of (estimate, reference). Returns a dict of error statistics."""
    diffs = [e - r for e, r in pairs]
    if not diffs:
        return None
    abs_diffs = [abs(d) for d in diffs]
    return {
        "n": len(diffs),
        "mae": statistics.mean(abs_diffs),
        "max_abs": max(abs_diffs),
        "bias": statistics.mean(diffs),
        "rmse": math.sqrt(statistics.mean(d * d for d in diffs)),
        "within_0_5": sum(a <= 0.5 for a in abs_diffs) / len(diffs),
    }


def probe_mean(row):
    reps = [num(row, f"probe_ph_{i}") for i in (1, 2, 3)]
    if any(r is None for r in reps):
        return None, "missing"
    if round(max(reps) - min(reps), 3) > REPLICATE_SPREAD_MAX:
        return None, "spread"
    return statistics.mean(reps), "ok"


def load_map(map_dir):
    try:
        from engine.map_service import MapService
        return MapService(map_dir)
    except (FileNotFoundError, ImportError) as error:
        print(f"Map comparison skipped: {error}")
        return None


def evaluate(rows, map_service, e_probe=None):
    per_sample, notes = [], []
    for row in rows:
        if not (row.get("lab_ph_water") or row.get("probe_ph_1")):
            continue                                         # empty template row
        probe, status = probe_mean(row)
        if status == "spread":
            notes.append(f"{row['sample_id']}: probe replicates spread more than {REPLICATE_SPREAD_MAX}; excluded from RQ1")
        lat, lon = num(row, "lat"), num(row, "lon")
        estimate = map_service.lookup(lat, lon) if (map_service and lat is not None and lon is not None) else None
        per_sample.append({
            "sample_id": row["sample_id"], "probe_ph": probe,
            "lab_ph_water": num(row, "lab_ph_water"), "lab_ph_cacl2": num(row, "lab_ph_cacl2"),
            "lab_oc_g_kg": None if num(row, "lab_oc_pct") is None else num(row, "lab_oc_pct") * 10,
            "lab_p_mg_kg": num(row, "lab_p_mg_kg"),
            "lab_k_mg_kg": None if num(row, "lab_k_cmol_kg") is None else num(row, "lab_k_cmol_kg") * K_CMOL_TO_MG,
            "lab_texture": (row.get("lab_texture") or "").strip() or None,
            "lab_p_method": (row.get("lab_p_method") or "").strip() or None,
            "map": estimate,
        })

    # RQ1: probe vs lab pH in water
    rq1 = errors_summary([(s["probe_ph"], s["lab_ph_water"]) for s in per_sample
                          if s["probe_ph"] is not None and s["lab_ph_water"] is not None])
    # Measured water - CaCl2 difference (replaces the unsourced 0.5-0.8)
    gaps = [s["lab_ph_water"] - s["lab_ph_cacl2"] for s in per_sample
            if s["lab_ph_water"] is not None and s["lab_ph_cacl2"] is not None]

    # Agreement uses the measured probe error when available (spec 2.4)
    e_used = e_probe if e_probe is not None else (rq1["max_abs"] if rq1 else DEFAULT_CONFIG.E_PROBE)
    for s in per_sample:
        m = s["map"]
        s["agrees"] = None
        if m is not None and s["probe_ph"] is not None:
            s["agrees"] = abs(s["probe_ph"] - m.ph_mean) <= e_used + m.ph_sd

    def compare(attr, lab_key, groups=(True, False)):
        out = {}
        for group in (None,) + tuple(groups):
            pairs = [(getattr(s["map"], attr), s[lab_key]) for s in per_sample
                     if s["map"] is not None and getattr(s["map"], attr) is not None
                     and s[lab_key] is not None and (group is None or s["agrees"] is group)]
            out[{None: "all", True: "agree", False: "disagree"}[group]] = errors_summary(pairs)
        return out

    rq2 = {
        "ph": compare("ph_mean", "lab_ph_water"),
        "oc_g_kg": compare("oc_g_kg", "lab_oc_g_kg"),
        "p_mg_kg": compare("p_ppm", "lab_p_mg_kg"),
        "k_mg_kg": compare("k_ppm", "lab_k_mg_kg"),
    }
    texture = {}
    for group in (None, True, False):
        pairs = [(s["map"].texture, s["lab_texture"]) for s in per_sample
                 if s["map"] is not None and s["map"].texture and s["lab_texture"]
                 and (group is None or s["agrees"] is group)]
        texture[{None: "all", True: "agree", False: "disagree"}[group]] = (
            (sum(a.lower() == b.lower() for a, b in pairs), len(pairs)) if pairs else None)
    return {"samples": per_sample, "rq1": rq1, "gaps": gaps, "e_used": e_used,
            "rq2": rq2, "texture": texture, "notes": notes}


def fmt(value, digits=2):
    return "–" if value is None else f"{value:.{digits}f}"


def report(result):
    lines = ["# Evaluation results", "",
             "Generated by `scripts/evaluate.py` from `docs/evaluation/samples.csv`.", ""]
    rq1 = result["rq1"]
    lines += ["## RQ1: probe pH against lab pH (water, 1:2.5)", ""]
    if rq1:
        verdict = "meets" if rq1["mae"] <= RQ1_TARGET_MAE else "does not meet"
        lines += [
            f"- Samples: {rq1['n']}",
            f"- Mean absolute error: **{fmt(rq1['mae'])}** pH ({verdict} the provisional target of {RQ1_TARGET_MAE})",
            f"- Largest absolute error: **{fmt(rq1['max_abs'])}** pH. Use this as `E_PROBE` (spec 2.4; provisional value 0.5)",
            f"- Bias (probe minus lab): {fmt(rq1['bias'])} pH",
            f"- RMSE: {fmt(rq1['rmse'])} pH; within 0.5 pH: {rq1['within_0_5']:.0%}", ""]
    else:
        lines += ["No samples with both probe and lab water pH yet.", ""]

    gaps = result["gaps"]
    lines += ["## Water pH minus CaCl2 pH (measured)", ""]
    if gaps:
        lines += [f"- Samples: {len(gaps)}",
                  f"- Mean {fmt(statistics.mean(gaps))}, range {fmt(min(gaps))} to {fmt(max(gaps))}"
                  + (f", SD {fmt(statistics.stdev(gaps))}" if len(gaps) > 1 else ""),
                  "- The agronomist's unsourced figure was 0.5 to 0.8. If the measured range differs, "
                  "update `PH_WATER_MINUS_CACL2` in `engine/config.py` and cite these results.", ""]
    else:
        lines += ["No samples with both water and CaCl2 pH yet.", ""]

    lines += ["## RQ2: iSDAsoil map against the lab", "",
              f"Agreement rule: |probe - map| <= E_PROBE + map SD, with E_PROBE = {fmt(result['e_used'])}.", ""]
    names = {"ph": "pH (water)", "oc_g_kg": "Organic carbon (g/kg)", "p_mg_kg": "P (mg/kg)", "k_mg_kg": "K (mg/kg)"}
    lines += ["| Property | Group | n | MAE | Bias (map - lab) |", "|---|---|---|---|---|"]
    for key, label in names.items():
        for group, stats in result["rq2"][key].items():
            if stats:
                lines.append(f"| {label} | {group} | {stats['n']} | {fmt(stats['mae'])} | {fmt(stats['bias'])} |")
            else:
                lines.append(f"| {label} | {group} | 0 | – | – |")
    lines.append("")
    lines += ["| Texture class | Group | Matches |", "|---|---|---|"]
    for group, value in result["texture"].items():
        lines.append(f"| USDA class | {group} | {f'{value[0]} of {value[1]}' if value else '–'} |")
    methods = {s["lab_p_method"] for s in result["samples"] if s["lab_p_method"]}
    if methods and methods != {"Mehlich-3"}:
        lines += ["", f"P was measured by {', '.join(sorted(methods))}; iSDAsoil P is modelled Mehlich-3, so the P comparison is indicative only."]
    if result["notes"]:
        lines += ["", "## Notes", ""] + [f"- {n}" for n in result["notes"]]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--samples", default="docs/evaluation/samples.csv")
    parser.add_argument("--out", default="docs/evaluation/results.md")
    parser.add_argument("--map-dir", default="data/isdasoil")
    parser.add_argument("--e-probe", type=float, help="override E_PROBE for the agreement split")
    args = parser.parse_args()

    with open(args.samples, newline="") as handle:
        rows = list(csv.DictReader(handle))
    result = evaluate(rows, load_map(args.map_dir), args.e_probe)
    Path(args.out).write_text(report(result))
    per_sample_path = Path(args.out).with_suffix(".csv")
    with per_sample_path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["sample_id", "probe_ph", "lab_ph_water", "lab_ph_cacl2", "map_ph", "map_sd", "agrees"])
        for s in result["samples"]:
            m = s["map"]
            writer.writerow([s["sample_id"], fmt(s["probe_ph"]), fmt(s["lab_ph_water"]), fmt(s["lab_ph_cacl2"]),
                             fmt(m.ph_mean if m else None), fmt(m.ph_sd if m else None), s["agrees"]])
    print(f"Wrote {args.out} and {per_sample_path}")


if __name__ == "__main__":
    main()
