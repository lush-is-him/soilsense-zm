"""Short scenario review sheet for the agronomist (RQ3), as an Excel workbook.

    python scripts/make_review_sheet.py            # docs/scenarios/review_sheet.xlsx

30 of the synthetic scenarios, chosen to cover every rule and edge case,
written in plain language. Sheet 1 asks the reviewer for their own advice
before they see the system's (so their judgement is independent); sheet 2
shows the system's advice with an Agree / Partly / Disagree column.
scripts/score_review.py reads the returned workbook.
"""

import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from engine.advice import Advisor  # noqa: E402
from engine.ruleset import load  # noqa: E402
from run_scenarios import run, scenarios  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "docs" / "scenarios" / "review_sheet.xlsx"
GRID = [(4.2, "maize"), (4.5, "soybean"), (4.9, "millet"), (4.9, "sunflower"), (5.2, "millet"),
        (5.5, "maize"), (5.5, "sunflower"), (5.8, "soybean"), (6.2, "sunflower"), (6.5, "maize"),
        (6.8, "maize"), (7.8, "soybean")]
VARIANTS = ["texture unknown", "clay", "sandy", "map agrees, map texture", "map disagrees, map texture",
            "late October", "lime too late this season", "irrigated"]
TRUST = {"none": "none (reading failed the quality check)", "low": "low (probe reading and field checks only)",
         "moderate": "moderate (probe agrees with the soil map)", "high": "high (laboratory result)"}
TIMING = {"ok": "apply 2-3 months before planting", "uncertain": "timing uncertain: may be too late this season",
          "too_late": "too late for this season; lime for next season", "any_time": "any time before planting (irrigated)"}


def pick():
    rows = scenarios()
    chosen = [r for r in rows if r["note"] == "grid" and (r["ph"], r["crop"]) in GRID]
    chosen += [r for r in rows if r["note"] in VARIANTS and
               ((r["ph"], r["crop"]) in {(5.2, "maize"), (4.9, "soybean")})]
    chosen += [r for r in rows if r["note"] in {"failed quality check", "lab result in CaCl2"}]
    return chosen


def describe_inputs(row):
    method = "CaCl2, laboratory" if row["method"] == "cacl2" else "water"
    texture = "not known" if not row["texture"] else f"{row['texture'].lower()} ({row['texture_source'].replace('_', ' ')})"
    return (f"Crop: {row['crop']}\nSoil pH: {row['ph']} ({method})\nTexture: {texture}\n"
            f"Confidence: {TRUST[row['trust']]}\nDate: {row['when']:%d %b %Y}; {row['water']}")


def amount(per_lima, unit="kg"):
    if not per_lima:
        return ""
    low, high = per_lima["low"], per_lima["high"]
    return f"{low:g} {unit}" if low == high else f"{low:g}-{high:g} {unit}"


def describe_advice(result):
    if result["trust_level"] == "none":
        return "No advice: retake the reading or enter a lab pH."
    lines = [r["text"] for r in result["refusal_text"]]
    plan_a = result["plan_a"] or {}
    if result["method_sensitive"]:
        lines.append("Plan A: no amounts (depends on the pH method); get a lab test before buying lime.")
    elif plan_a.get("status") == "ok":
        lime = plan_a["lime"]
        if lime["status"] == "not_needed":
            lime_text = "no lime needed"
        elif lime.get("rate_t_ha"):
            lo, hi = lime["rate_t_ha"]
            lime_text = (f"{'optional, ' if lime['status'] == 'optional' else ''}{lo:g}-{hi:g} t/ha "
                         f"({amount(lime['per_lima'])} per lima), {TIMING.get(lime['timing'], '')}")
        else:
            lime_text = "amount needs the soil texture"
        fert = plan_a["fertiliser"]
        def rate(item):
            return f"{item['product']} {amount(item.get('per_lima'))} per lima" if item.get("per_lima") else f"{item['product']} (rate not available)"
        lines.append(f"Plan A: lime {lime_text}; basal {rate(fert['basal'])}; top dressing {rate(fert['top_dress'])}; "
                     f"manure {amount(plan_a['manure'], 't')} per lima.")
    elif plan_a.get("status"):
        lines.append(f"Plan A: {plan_a['status'].replace('_', ' ')}.")
    plan_b = result["plan_b"] or {}
    if plan_b.get("status") == "ok":
        parts = []
        for item in plan_b["items"]:
            if item["item"] == "lime":
                parts.append("lime not needed" if item.get("status") == "not_needed"
                             else f"lime {item.get('g_per_station', [''])[0]} g per planting station ({amount(item['per_lima'])} per lima)")
            elif item["item"] == "fertiliser":
                parts.append(f"fertiliser {amount(item.get('per_lima')) or '(rate not available)'} per lima")
            elif item["item"] == "manure":
                parts.append(f"manure {amount(item['per_lima'], 't')} per lima")
            else:
                parts.append("certified seed")
        lines.append("Plan B (buy in this order as money allows): " + "; ".join(parts) + ".")
    crops = (result["plan_c"] or {}).get("crops", [])
    lines.append("Plan C (grows in this soil now): " + (", ".join(crops) if crops else "none; get a lab test") + ".")
    return "\n".join(lines)


def build(path=OUT):
    advisor = Advisor(load())
    chosen = pick()
    wb = Workbook()
    wrap = Alignment(wrap_text=True, vertical="top")
    bold = Font(bold=True)
    fill = PatternFill("solid", fgColor="E8F1EA")

    intro = wb.active
    intro.title = "Read me"
    for i, text in enumerate([
        "SoilSense ZM: scenario review",
        "",
        "Thank you for reviewing. There are 30 made-up farm situations (not real farmers).",
        "1. Sheet 'Your advice': for each situation, write what you would advise. Please do this first,",
        "   before looking at the next sheet, so your advice is your own.",
        "2. Sheet 'System advice': read what SoilSense ZM advises, then choose Agree, Partly or Disagree,",
        "   and say what is wrong if you do not fully agree.",
        "Short answers are fine. 1 lima = 0.25 ha. pH is in water unless it says CaCl2.",
        "When finished, save the file and send it back.",
    ], start=1):
        intro.cell(row=i, column=1, value=text).font = Font(bold=(i == 1), size=14 if i == 1 else 11)
    intro.column_dimensions["A"].width = 100

    mine = wb.create_sheet("Your advice")
    mine.append(["No.", "Situation", "Your advice (lime, fertiliser, crops)"])
    system = wb.create_sheet("System advice")
    system.append(["No.", "Situation", "SoilSense ZM advice", "Agree, Partly or Disagree?", "If not Agree: what is wrong?", "id"])
    for sheet in (mine, system):
        for cell in sheet[1]:
            cell.font, cell.fill, cell.alignment = bold, fill, wrap
    for n, row in enumerate(chosen, start=1):
        situation = describe_inputs(row)
        mine.append([n, situation, ""])
        system.append([n, situation, describe_advice(run(advisor, row)), "", "", row["id"]])
    for sheet, widths in ((mine, [6, 42, 70]), (system, [6, 42, 70, 16, 45, 8])):
        for col, width in zip("ABCDEF", widths):
            sheet.column_dimensions[col].width = width
        for line in sheet.iter_rows(min_row=2):
            for cell in line:
                cell.alignment = wrap
        sheet.freeze_panes = "A2"
    system.column_dimensions["F"].hidden = True
    choice = DataValidation(type="list", formula1='"Agree,Partly,Disagree"', allow_blank=True)
    system.add_data_validation(choice)
    choice.add(f"D2:D{len(chosen) + 1}")
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path, len(chosen)


if __name__ == "__main__":
    out, count = build()
    print(f"Wrote {out} ({count} scenarios)")
