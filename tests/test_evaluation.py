"""Evaluation scripts: RQ1/RQ2 maths, RQ3 scoring, SUS."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import evaluate  # noqa: E402
import score_review  # noqa: E402
import sus  # noqa: E402
from engine.map_service import MapEstimate  # noqa: E402


class FakeMap:
    def lookup(self, lat, lon):
        return MapEstimate(6.0, 0.2, 7.0, 7.0, 160.0, "Loam")


def row(sid, probe, water, cacl2=None, **extra):
    base = {"sample_id": sid, "lat": "-15.7", "lon": "28.2",
            "probe_ph_1": str(probe), "probe_ph_2": str(probe), "probe_ph_3": str(probe),
            "lab_ph_water": str(water), "lab_ph_cacl2": "" if cacl2 is None else str(cacl2)}
    return {**base, **extra}


def test_rq1_errors_and_e_probe():
    rows = [row("S01", 5.5, 5.3), row("S02", 6.0, 6.4), row("S03", 6.1, 6.1)]
    result = evaluate.evaluate(rows, None)
    assert result["rq1"]["n"] == 3
    assert result["rq1"]["mae"] == pytest.approx(0.2)
    assert result["rq1"]["max_abs"] == pytest.approx(0.4)
    assert result["e_used"] == pytest.approx(0.4)


def test_replicate_spread_excluded():
    bad = row("S01", 5.5, 5.3, probe_ph_3="5.8")
    result = evaluate.evaluate([bad, row("S02", 6.0, 6.0)], None)
    assert result["rq1"]["n"] == 1 and "S01" in result["notes"][0]


def test_measured_water_cacl2_gap():
    result = evaluate.evaluate([row("S01", 5.5, 5.5, 4.9), row("S02", 6.0, 6.0, 5.2)], None)
    assert result["gaps"] == pytest.approx([0.6, 0.8])


def test_rq2_split_by_agreement_and_unit_conversion():
    rows = [row("S01", 6.1, 6.2, lab_oc_pct="0.8", lab_k_cmol_kg="0.4", lab_texture="loam"),
            row("S02", 4.8, 5.0, lab_texture="Clay")]
    result = evaluate.evaluate(rows, FakeMap(), e_probe=0.5)
    assert [s["agrees"] for s in result["samples"]] == [True, False]
    assert result["rq2"]["oc_g_kg"]["all"]["bias"] == pytest.approx(7.0 - 8.0)
    assert result["rq2"]["k_mg_kg"]["all"]["bias"] == pytest.approx(160 - 0.4 * 391)
    assert result["texture"]["agree"] == (1, 1) and result["texture"]["disagree"] == (0, 1)
    text = evaluate.report(result)
    assert "RQ1" in text and "RQ2" in text


def test_empty_template_rows_ignored():
    assert evaluate.evaluate([{"sample_id": "S01"}], None)["samples"] == []


def test_review_scoring():
    rows = [{"id": "S1", "note": "grid", "agronomist_agrees": "yes"},
            {"id": "S2", "note": "grid", "agronomist_agrees": "partial", "ph": "5", "crop": "maize"},
            {"id": "S3", "note": "clay", "agronomist_agrees": ""}]
    answered, by_note, disagreements = score_review.score(rows)
    assert sum(answered) / len(answered) == 0.75 and len(disagreements) == 1


@pytest.mark.parametrize("answers, expected", [([5, 1] * 5, 100.0), ([1, 5] * 5, 0.0), ([3] * 10, 50.0)])
def test_sus_score(answers, expected):
    assert sus.sus_score(answers) == expected


def test_sus_rejects_bad_answers():
    with pytest.raises(ValueError):
        sus.sus_score([6] * 10)


def test_short_review_workbook_round_trip(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    import make_review_sheet
    path, count = make_review_sheet.build(tmp_path / "sheet.xlsx")
    assert count == 30
    wb = openpyxl.load_workbook(path)
    sheet = wb["System advice"]
    for i, row in enumerate(sheet.iter_rows(min_row=2), start=0):
        row[3].value = ["Agree", "Partly", "Disagree", "Agree"][i % 4]
    wb.save(path)
    answered, _, disagreements = score_review.score(score_review.rows_from_workbook(path))
    assert len(answered) == 30 and len(disagreements) == 15


def test_review_form_csv_scoring(tmp_path):
    import json
    keys = json.loads((Path(__file__).resolve().parent.parent / "docs" / "scenarios" / "review_keys.json").read_text())
    header = ["Timestamp"] + [f"A{n}. Situation {n}: your advice" for n in keys] \
        + [f"R{n}. Situation {n}: do you agree?" for n in keys] + [f"C{n}. Situation {n}: if not Agree, what is wrong?" for n in keys]
    answers = ["Agree"] * (len(keys) - 2) + ["Partly", "Disagree"]
    row = ["2026-11-20"] + ["my advice"] * len(keys) + answers + [""] * len(keys)
    path = tmp_path / "responses.csv"
    import csv
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerow(row)
    answered, _, disagreements = score_review.score(score_review.rows_from_form_csv(path))
    assert len(answered) == 30 and sum(answered) == 28.5 and len(disagreements) == 2


def test_move_sample_fixes_a_wrong_code(tmp_path):
    import sys
    sys.path.insert(0, "scripts")
    from move_sample import move
    path = tmp_path / "samples.csv"
    path.write_text("sample_id,probe_ph_1,probe_ph_2,probe_ph_3,probe_temp_c,notes\n"
                    "S06,,,,,\nS09,8.83,8.82,8.84,25.0,\n")
    move("S09", "S06", path)
    lines = path.read_text().splitlines()
    assert lines[1].startswith("S06,8.83,8.82,8.84,25.0,") and lines[2] == "S09,,,,,"
