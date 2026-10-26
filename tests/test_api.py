"""API end to end: auth, fields (30 m rule), calibration, readings, advice (S1-2..S1-5, spec 4)."""

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from backend import db as backend_db  # noqa: E402
from backend.routes import fields as fields_routes  # noqa: E402
from backend.seed import seed  # noqa: E402
from engine.map_service import MapEstimate  # noqa: E402


class FakeMap:
    def __init__(self, estimate):
        self.estimate = estimate

    def lookup(self, lat, lon):
        return self.estimate


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SEED_OPERATOR_PASSWORD", "operator-pass")
    monkeypatch.setenv("SEED_AGRONOMIST_PASSWORD", "agronomist-pass")
    monkeypatch.setenv("SEED_ADMIN_PASSWORD", "admin-pass")
    conn = backend_db.connect(tmp_path / "test.db")
    seed(conn)
    backend_db.set_db(conn)
    fields_routes.set_map_service(FakeMap(MapEstimate(5.4, 0.2, 7.0, 7.0, 160.0, "Clay Loam")))
    from backend.main import app
    with TestClient(app) as c:
        yield c
    fields_routes.set_map_service(None)
    backend_db.set_db(None)


def login(client, user="operator"):
    r = client.post("/auth/login", json={"username": user, "password": f"{user}-pass"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture
def op(client):
    return login(client)


def make_field(client, op, **overrides):
    farmer = client.post("/farmers", json={"alias": "Test farmer"}, headers=op).json()
    body = {"farmer_id": farmer["farmer_id"], "name": "F1", "lat": -15.63, "lon": 28.24,
            "gps_accuracy_m": 8, "location_source": "gps", **overrides}
    return client.post("/fields", json=body, headers=op)


def calibrate(client, op, mv7=0.0, mv4=177.5, temp=25.0):
    return client.post("/devices/probe-1/calibrations",
                       json={"mv_ph7": mv7, "mv_ph4": mv4, "temp_c": temp}, headers=op).json()


# ----- auth -----

def test_login_required(client):
    assert client.get("/farmers").status_code == 401


def test_wrong_password_rejected(client):
    assert client.post("/auth/login", json={"username": "operator", "password": "x"}).status_code == 401


def test_passwords_are_hashed(client):
    row = backend_db._override.execute("SELECT password_hash FROM users WHERE username='operator'").fetchone()
    assert row["password_hash"].startswith("scrypt$") and "operator-pass" not in row["password_hash"]


def test_rules_need_agronomist_or_admin(client, op):
    assert client.get("/rules", headers=op).status_code == 403
    r = client.get("/rules", headers=login(client, "agronomist"))
    assert r.status_code == 200 and any(i["rule"] == "LIME-TRIGGER" for i in r.json()["open_items"])


def test_tampered_token_rejected(client, op):
    bad = {"Authorization": op["Authorization"][:-2] + "xx"}
    assert client.get("/auth/me", headers=bad).status_code == 401


# ----- farmers and privacy (NFR5) -----

def test_phone_needs_consent(client, op):
    r = client.post("/farmers", json={"alias": "A", "phone": "+260971234567"}, headers=op)
    assert r.status_code == 422


def test_phone_can_be_deleted(client, op):
    f = client.post("/farmers", json={"alias": "A", "phone": "+260971234567", "sms_consent": True},
                    headers=op).json()
    r = client.delete(f"/farmers/{f['farmer_id']}/phone", headers=op).json()
    assert r["phone"] is None and r["sms_consent"] is False


# ----- fields and GPS (S1-3) -----

def test_45m_fix_rejected(client, op):
    assert make_field(client, op, gps_accuracy_m=45).status_code == 422


def test_30m_fix_accepted(client, op):
    assert make_field(client, op, gps_accuracy_m=30).status_code == 201


def test_manual_pin_stored_as_manual(client, op):
    r = make_field(client, op, location_source="manual", gps_accuracy_m=None)
    assert r.status_code == 201 and r.json()["location_source"] == "manual"


def test_map_estimate_cached_per_field(client, op):
    field = make_field(client, op).json()
    first = client.get(f"/fields/{field['field_id']}/map-estimate", headers=op).json()
    second = client.get(f"/fields/{field['field_id']}/map-estimate", headers=op).json()
    assert first["ph_mean"] == 5.4 and first["estimate_id"] == second["estimate_id"]


# ----- calibration and readings (S1-4b, S1-5) -----

@pytest.mark.parametrize("mv4, accepted", [(177.5, True), (166.0, False), (190.0, False)])
def test_calibration_slope_checked(client, op, mv4, accepted):
    cal = calibrate(client, op, mv4=mv4)
    assert cal["accepted"] is accepted


def test_reading_from_bridge_converted_with_calibration(client, op):
    calibrate(client, op)
    field = make_field(client, op).json()
    # 5.5 pH at 100% slope, 25 C: (7 - 5.5) * 59.16 mV = 88.7 mV
    r = client.post("/readings", json={"field_id": field["field_id"], "device_id": "probe-1",
                                       "replicates_mv": [88.7, 89.0, 88.4], "temp_c": 25.0},
                    headers=op).json()
    assert r["quality_status"] == "accepted" and r["ph_water"] == pytest.approx(5.5, abs=0.02)


def test_reading_without_valid_calibration_rejected(client, op):
    calibrate(client, op, mv4=150.0)               # failed calibration
    field = make_field(client, op).json()
    r = client.post("/readings", json={"field_id": field["field_id"], "device_id": "probe-1",
                                       "replicates_ph": [5.5, 5.5, 5.5], "temp_c": 25.0},
                    headers=op).json()
    assert r["quality_status"] == "rejected" and "no valid calibration" in r["quality_reasons"]


def test_reading_spread_rejected(client, op):
    calibrate(client, op)
    field = make_field(client, op).json()
    r = client.post("/readings", json={"field_id": field["field_id"], "device_id": "probe-1",
                                       "replicates_ph": [5.4, 5.5, 5.6], "temp_c": 25.0},
                    headers=op).json()
    assert r["quality_status"] == "rejected" and r["ph_water"] is None
    history = client.get(f"/fields/{field['field_id']}/history", headers=op).json()
    assert history["readings"][0]["quality_reasons"] == r["quality_reasons"]


# ----- advice (FR7, FR10, NFR2) -----

def reading(client, op, field_id, ph, temp=25.0):
    return client.post("/readings", json={"field_id": field_id, "device_id": "probe-1",
                                          "replicates_ph": [ph, ph, ph], "temp_c": temp},
                       headers=op).json()


def test_failed_reading_gets_no_advice(client, op):
    calibrate(client, op)
    field = make_field(client, op).json()
    bad = reading(client, op, field["field_id"], 5.5, temp=40.0)
    r = client.post("/advice", json={"field_id": field["field_id"], "reading_id": bad["reading_id"],
                                     "crop": "maize"}, headers=op).json()
    assert r["trust_level"] == "none" and r["refusals"] == ["REF-01"] and r["plan_a"] is None


def test_map_agreement_gives_moderate_and_uses_map_texture(client, op):
    calibrate(client, op)
    field = make_field(client, op).json()
    good = reading(client, op, field["field_id"], 5.6)          # map 5.4 +/- 0.7
    r = client.post("/advice", json={"field_id": field["field_id"], "reading_id": good["reading_id"],
                                     "crop": "maize", "as_of_date": "2026-08-01"}, headers=op).json()
    assert r["trust"]["level"] == "moderate"
    assert r["texture"] == {"value": "Clay Loam", "source": "map"}
    assert r["map_estimate"]["ph_mean"] == 5.4


def test_manual_location_low_trust_needs_field_check(client, op):
    calibrate(client, op)
    field = make_field(client, op, location_source="manual", gps_accuracy_m=None).json()
    good = reading(client, op, field["field_id"], 6.4)
    body = {"field_id": field["field_id"], "reading_id": good["reading_id"], "crop": "maize",
            "as_of_date": "2026-08-01"}
    first = client.post("/advice", json=body, headers=op).json()
    assert first["trust_level"] == "low" and "REF-03" in first["refusals"]
    client.post(f"/fields/{field['field_id']}/checks", json={"texture_by_feel": "loamy"}, headers=op)
    second = client.post("/advice", json=body, headers=op).json()
    assert second["plan_a"]["lime"]["rate_t_ha"] == [0.5, 1.0]


def test_lab_result_gives_high_trust(client, op):
    field = make_field(client, op).json()
    client.post(f"/fields/{field['field_id']}/lab-results",
                json={"ph": 6.0, "ph_method": "water", "texture": "Loam"}, headers=op)
    r = client.post("/advice", json={"field_id": field["field_id"], "crop": "maize"}, headers=op).json()
    assert r["trust_level"] == "high" and r["ph_method_input"] == "water"


def test_advice_saved_with_rule_versions_and_rerendered(client, op):
    field = make_field(client, op).json()
    client.post(f"/fields/{field['field_id']}/lab-results",
                json={"ph": 6.0, "ph_method": "water", "texture": "Loam"}, headers=op)
    rec = client.post("/advice", json={"field_id": field["field_id"], "crop": "maize"}, headers=op).json()
    saved = client.get(f"/advice/{rec['rec_id']}?lang=ny", headers=op).json()
    assert saved["rule_versions"]["BAND-01"] == 1
    assert all(m["reviewed"] is False for m in saved["messages"])   # no reviewed Nyanja yet


def test_sms_needs_consent(client, op):
    field = make_field(client, op).json()
    client.post(f"/fields/{field['field_id']}/lab-results", json={"ph": 6.0, "ph_method": "water"},
                headers=op)
    rec = client.post("/advice", json={"field_id": field["field_id"], "crop": "maize"}, headers=op).json()
    assert client.post(f"/advice/{rec['rec_id']}/sms", headers=op).status_code == 409


def test_advice_needs_reading_or_lab(client, op):
    field = make_field(client, op).json()
    assert client.post("/advice", json={"field_id": field["field_id"], "crop": "maize"},
                       headers=op).status_code == 422
