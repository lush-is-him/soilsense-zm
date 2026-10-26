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
