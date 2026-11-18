"""Lab anchor and per-point lab results (ZARI results, Nov 2026)."""

import pytest

from engine.anchor import anchor_offset, lab_in_water
from tests.test_api import client, login, make_field, calibrate  # noqa: F401  (fixtures and helpers)

# Four of the real Shimabala pairs: probe (water) and ZARI (CaCl2)
PAIRS = [("S01", 8.55, 6.94), ("S02", 7.73, 6.89), ("S04", 6.91, 5.96), ("S05", 7.59, 6.01)]


def test_offset_is_in_the_water_scale():
    anchor = anchor_offset([(8.55, 6.94, "cacl2"), (7.73, 6.89, "cacl2")])
    expected = ((8.55 - 6.94 - 0.65) + (7.73 - 6.89 - 0.65)) / 2
    assert anchor.offset == pytest.approx(expected, abs=0.01) and anchor.n == 2
    assert lab_in_water(6.0, "water") == 6.0


def test_one_pair_is_not_enough():
    assert anchor_offset([(8.55, 6.94, "cacl2")]) is None


@pytest.fixture
def plot(client):
    op = login(client)
    calibrate(client, op)
    field = make_field(client, op).json()
    for label, probe, _ in PAIRS:
        r = client.post("/readings", json={"field_id": field["field_id"], "device_id": "probe-1",
                                           "replicates_ph": [probe] * 3, "temp_c": 25, "point_label": label},
                        headers=op)
        assert r.status_code == 201 and r.json()["quality_status"] == "accepted", r.text
    return op, field


def add_lab(client, op, field_id, label, ph, p=2.0):
    r = client.post(f"/fields/{field_id}/lab-results", json={"ph": ph, "ph_method": "cacl2", "point_label": label,
                                                             "p": p, "lab_name": "ZARI"}, headers=op)
    assert r.status_code == 201, r.text
    return r.json()


def device(client, op):
    return next(d for d in client.get("/devices", headers=op).json() if d["device_id"] == "probe-1")


def test_lab_results_teach_the_probe_its_offset(client, plot):
    op, field = plot
    add_lab(client, op, field["field_id"], "S01", 6.94)
    assert device(client, op)["lab_offset"] is None                   # one pair: not yet
    add_lab(client, op, field["field_id"], "s02", 6.89)              # labels match whatever the case
    d = device(client, op)
    assert d["lab_offset_n"] == 2 and d["lab_offset"] == pytest.approx(0.58, abs=0.01)
    # earlier readings are corrected, and the raw value is kept
    points = {p["label"]: p["ph"] for p in client.get(f"/fields/{field['field_id']}/history", headers=op).json()["points"]}
    assert points["S01"] == pytest.approx(8.55 - 0.58, abs=0.01)


def test_new_readings_and_the_live_view_use_the_offset(client, plot):
    op, field = plot
    for label, _, lab in PAIRS:
        add_lab(client, op, field["field_id"], label, lab)
    offset = device(client, op)["lab_offset"]
    r = client.post("/readings", json={"field_id": field["field_id"], "device_id": "probe-1",
                                       "replicates_ph": [7.5] * 3, "temp_c": 25}, headers=op).json()
    assert r["ph_water"] == pytest.approx(7.5 - offset, abs=0.01) and r["lab_offset"] == offset
    live = client.post("/devices/probe-1/live", json={"mv": 0.0, "temp_c": 25.0}, headers=op).json()
    assert live["ph"] == pytest.approx(7.0 - offset, abs=0.02)


def test_relearning_does_not_compound(client, plot):
    op, field = plot
    for label, _, lab in PAIRS[:2]:
        add_lab(client, op, field["field_id"], label, lab)
    first = device(client, op)["lab_offset"]
    for label, _, lab in PAIRS[2:]:
        add_lab(client, op, field["field_id"], label, lab)
    second = device(client, op)["lab_offset"]
    points = {p["label"]: p["ph"] for p in client.get(f"/fields/{field['field_id']}/history", headers=op).json()["points"]}
    assert points["S01"] == pytest.approx(8.55 - second, abs=0.01) and first != second


def test_whole_field_advice_uses_the_median_of_the_lab_points(client, plot):
    op, field = plot
    for label, _, lab in PAIRS:
        add_lab(client, op, field["field_id"], label, lab)
    r = client.post("/advice", json={"field_id": field["field_id"], "whole_field": True, "crop": "maize",
                                     "as_of_date": "2026-11-10"}, headers=op).json()
    assert r["trust_level"] == "high"
    assert r["lab"]["n_points"] == 4 and r["lab"]["ph"] == pytest.approx(6.45, abs=0.01)
    assert any(m["key"] == "msg.MSG-12" for m in r["messages"])      # P 2 mg: keep the basal fertiliser


def test_one_point_uses_its_own_lab_result(client, plot):
    op, field = plot
    for label, _, lab in PAIRS:
        add_lab(client, op, field["field_id"], label, lab)
    readings = client.get(f"/fields/{field['field_id']}/history", headers=op).json()["points"]
    s04 = next(p for p in readings if p["label"] == "S04")
    r = client.post("/advice", json={"field_id": field["field_id"], "reading_id": s04["reading_id"], "crop": "maize",
                                     "as_of_date": "2026-11-10"}, headers=op).json()
    assert r["lab"]["point_label"] == "S04" and r["lab"]["ph"] == 5.96
