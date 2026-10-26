"""Generate the synthetic scenario suite and run the engine on it (spec 10, RQ3).

Writes a CSV with the inputs, the engine's output and blank columns for the
agronomist's own recommendation, so a reviewer can fill it in for RQ3.
All scenarios are synthetic.

    python scripts/run_scenarios.py                       # docs/scenarios/scenarios.csv
    python scripts/run_scenarios.py --compare-methods     # which scenarios change
                                                          # if the bands are water vs CaCl2
"""

import argparse
import copy
import csv
import sys
from datetime import date
from itertools import product
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.advice import AdviceRequest, Advisor  # noqa: E402
from engine.ruleset import load  # noqa: E402

PH_VALUES = [4.2, 4.5, 4.9, 5.2, 5.5, 5.8, 6.2, 6.5, 6.8, 7.8]
CROPS = ["maize", "soybean", "sunflower", "millet"]


def scenarios():
    """About 90 scenarios covering the cases spec 10 lists."""
    rows = []
    # Core grid: every pH against every crop, loamy texture, before the season.
    for ph, crop in product(PH_VALUES, CROPS):
        rows.append(dict(ph=ph, crop=crop, trust="low", texture="loamy",
                         texture_source="field_check", water="rainfed", when=date(2026, 8, 1),
                         budget="low", note="grid"))
    # Texture, trust, timing, water and budget variations on maize and soybean.
    for ph, crop in product([4.9, 5.2, 5.8], ["maize", "soybean"]):
        base = dict(ph=ph, crop=crop, trust="low", texture="loamy", texture_source="field_check",
                    water="rainfed", when=date(2026, 8, 1), budget="low")
        rows += [
            {**base, "texture": None, "texture_source": None, "note": "texture unknown"},
            {**base, "texture": "clay", "note": "clay"},
            {**base, "texture": "sandy", "note": "sandy"},
            {**base, "texture": "Clay Loam", "texture_source": "map", "trust": "moderate",
             "note": "map agrees, map texture"},
            {**base, "texture": "Clay Loam", "texture_source": "map", "note": "map disagrees, map texture"},
            {**base, "when": date(2026, 10, 25), "note": "late October"},
            {**base, "when": date(2026, 12, 15), "note": "lime too late this season"},
            {**base, "when": date(2026, 12, 15), "water": "irrigated", "note": "irrigated"},
            {**base, "budget": "medium", "note": "medium budget"},
        ]
    # Failed reading and lab entry.
    rows.append(dict(ph=5.2, crop="maize", trust="none", texture="loamy",
                     texture_source="field_check", water="rainfed", when=date(2026, 8, 1),
                     budget="low", note="failed quality check"))
    rows.append(dict(ph=4.7, crop="maize", trust="high", texture="Clay", texture_source="lab",
                     water="rainfed", when=date(2026, 8, 1), budget="low",
                     note="lab result in CaCl2", method="cacl2"))
    for i, row in enumerate(rows, start=1):
        row["id"] = f"S{i:03d}"
        row.setdefault("method", "water")
    return rows


def run(advisor, row):
    return advisor.advise(AdviceRequest(
        ph=row["ph"], ph_method=row["method"], trust_level=row["trust"], crop=row["crop"],
        as_of_date=row["when"], water=row["water"], budget_band=row["budget"],
        texture=row["texture"], texture_source=row["texture_source"]))


def summarise(result):
    plan_a = result["plan_a"] or {}
    lime = plan_a.get("lime") or {}
    rate = lime.get("rate_t_ha")
    return {
        "refusals": " ".join(result["refusals"]),
        "method_sensitive": result["method_sensitive"],
        "plan_a_status": plan_a.get("status", ""),
        "lime_status": lime.get("status", ""),
        "lime_t_ha": f"{rate[0]}-{rate[1]}" if rate else "",
        "lime_timing": lime.get("timing", ""),
        "plan_b": (result["plan_b"] or {}).get("status", ""),
        "plan_c": " ".join((result["plan_c"] or {}).get("crops", [])),
        "fired_rules": " ".join(r["id"] for r in result["fired_rules"]),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default="docs/scenarios/scenarios.csv")
    parser.add_argument("--compare-methods", action="store_true")
    args = parser.parse_args()

    rules = load()
    rows = scenarios()

    if args.compare_methods:
        outputs = {}
        for method in ("water", "cacl2"):
            variant = copy.deepcopy(rules)
            variant["BAND-01"].ph_method = method
            advisor = Advisor(variant)
            outputs[method] = {r["id"]: summarise(run(advisor, r)) for r in rows}
        changed = [r for r in rows if outputs["water"][r["id"]] != outputs["cacl2"][r["id"]]]
        print(f"{len(changed)} of {len(rows)} scenarios change if the bands are CaCl2 instead of water:")
        for r in changed:
            w, c = outputs["water"][r["id"]], outputs["cacl2"][r["id"]]
            print(f"  {r['id']} pH {r['ph']} {r['crop']:9} ({r['note']}): "
                  f"water -> {w['lime_status'] or w['refusals'] or '-'} [{w['plan_c']}] | "
                  f"CaCl2 -> {c['lime_status'] or c['refusals'] or '-'} [{c['plan_c']}]")
        return

    advisor = Advisor(rules)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fields = ["id", "note", "ph", "method", "crop", "trust", "texture", "texture_source",
              "water", "when", "budget", "refusals", "method_sensitive", "plan_a_status",
              "lime_status", "lime_t_ha", "lime_timing", "plan_b", "plan_c", "fired_rules",
              "agronomist_recommendation", "agronomist_agrees", "agronomist_comment"]
    with out.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({**{k: row.get(k) for k in fields if k in row},
                             **summarise(run(advisor, row)),
                             "agronomist_recommendation": "", "agronomist_agrees": "",
                             "agronomist_comment": ""})
    print(f"Wrote {len(rows)} synthetic scenarios to {out}")


if __name__ == "__main__":
    main()
