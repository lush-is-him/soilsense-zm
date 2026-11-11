"""Roles and data ownership (self-testing model, Nov 2026): farmer, officer, admin."""

import sqlite3

import pytest

from backend import db as backend_db
from tests.test_api import client, login, make_field, calibrate, reading  # noqa: F401  (fixtures and helpers)


def signup(client, username, share=False, **extra):
    body = {"full_name": f"Farmer {username}", "username": username, "password": "farmer-pass-1",
            "village": "Shimabala", "share_consent": share, **extra}
    r = client.post("/auth/signup", json=body)
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}, r.json()["user"]


def own_field(client, headers, name="My field"):
    r = client.post("/fields", json={"name": name, "lat": -15.68, "lon": 28.22, "gps_accuracy_m": 4,
                                     "location_source": "gps"}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def test_signup_creates_a_farmer_with_their_own_profile(client):
    headers, user = signup(client, "sibalo")
    assert user["role"] == "farmer" and user["farmer_id"]
    me = client.get("/farmers/me", headers=headers).json()
    assert me["alias"] == "Farmer sibalo" and me["village"] == "Shimabala" and me["can_edit"]


def test_signup_username_must_be_free(client):
    signup(client, "sibalo")
    r = client.post("/auth/signup", json={"full_name": "X Y", "username": "sibalo", "password": "another-pass"})
    assert r.status_code == 409


def test_farmer_sees_only_their_own_farm(client):
    a, _ = signup(client, "farmer_a")
    b, _ = signup(client, "farmer_b")
    field_a = own_field(client, a)
    assert [f["alias"] for f in client.get("/farmers", headers=a).json()] == ["Farmer farmer_a"]
    assert client.get(f"/fields/{field_a['field_id']}", headers=b).status_code == 404
    assert client.get(f"/fields/{field_a['field_id']}/history", headers=b).status_code == 404
    assert client.post("/readings", json={"field_id": field_a["field_id"], "replicates_ph": [6, 6, 6],
                                          "temp_c": 25}, headers=b).status_code == 404


def test_farmer_cannot_add_fields_to_someone_else(client):
    a, user_a = signup(client, "farmer_a")
    b, _ = signup(client, "farmer_b")
    r = client.post("/fields", json={"farmer_id": user_a["farmer_id"], "name": "x", "lat": -15.6, "lon": 28.2,
                                     "location_source": "manual"}, headers=b)
    assert r.status_code == 404


def test_farmer_cannot_register_other_farmers(client):
    a, _ = signup(client, "farmer_a")
    assert client.post("/farmers", json={"alias": "Someone"}, headers=a).status_code == 403


def test_officer_sees_shared_and_own_registered_farmers_only(client):
    officer = login(client)
    signup(client, "private_farmer", share=False)
    signup(client, "sharing_farmer", share=True)
    client.post("/farmers", json={"alias": "Walk-in farmer"}, headers=officer)
    names = {f["alias"] for f in client.get("/farmers", headers=officer).json()}
    assert "Farmer sharing_farmer" in names and "Walk-in farmer" in names
    assert "Farmer private_farmer" not in names


def test_asking_for_help_makes_a_private_farm_visible_to_officers(client):
    officer = login(client)
    farmer, _ = signup(client, "private_farmer", share=False)
    field = own_field(client, farmer)
    assert client.get(f"/fields/{field['field_id']}", headers=officer).status_code == 404
    r = client.post("/referrals", json={"field_id": field["field_id"], "kind": "visit",
                                        "reason": "Please test for me"}, headers=farmer)
    assert r.status_code == 201
    assert client.get(f"/fields/{field['field_id']}", headers=officer).status_code == 200
    assert [x["field_id"] for x in client.get("/referrals", headers=officer).json()] == [field["field_id"]]


def test_lab_referral_closed_by_officer_entering_the_result(client):
    officer = login(client)
    farmer, _ = signup(client, "farmer_a", share=True)
    field = own_field(client, farmer)
    ref = client.post("/referrals", json={"field_id": field["field_id"], "kind": "lab"}, headers=farmer).json()
    assert ref["status"] == "open"
    r = client.post(f"/fields/{field['field_id']}/lab-results",
                    json={"ph": 7.4, "ph_method": "water", "lab_name": "ZARI Mount Makulu",
                          "referral_id": ref["referral_id"]}, headers=officer)
    assert r.status_code == 201
    done = client.get(f"/referrals/{ref['referral_id']}", headers=farmer).json()
    assert done["status"] == "done" and done["handled_by_name"]
    advice = client.post("/advice", json={"field_id": field["field_id"], "crop": "maize"}, headers=farmer).json()
    assert advice["trust_level"] == "high"


def test_farmer_can_only_cancel_a_referral(client):
    farmer, _ = signup(client, "farmer_a")
    field = own_field(client, farmer)
    ref = client.post("/referrals", json={"field_id": field["field_id"], "kind": "lab"}, headers=farmer).json()
    assert client.patch(f"/referrals/{ref['referral_id']}", json={"status": "done"}, headers=farmer).status_code == 403
    assert client.patch(f"/referrals/{ref['referral_id']}", json={"status": "cancelled"},
                        headers=farmer).json()["status"] == "cancelled"


def test_same_open_referral_is_not_duplicated(client):
    farmer, _ = signup(client, "farmer_a")
    field = own_field(client, farmer)
    first = client.post("/referrals", json={"field_id": field["field_id"], "kind": "lab"}, headers=farmer).json()
    again = client.post("/referrals", json={"field_id": field["field_id"], "kind": "lab"}, headers=farmer).json()
    assert first["referral_id"] == again["referral_id"]


def test_farmer_edits_own_profile_with_consent_rules(client):
    farmer, user = signup(client, "farmer_a")
    fid = user["farmer_id"]
    assert client.patch(f"/farmers/{fid}", json={"phone": "+260971234567"}, headers=farmer).status_code == 422
    r = client.patch(f"/farmers/{fid}", json={"phone": "+260971234567", "sms_consent": True,
                                               "village": "Chilanga", "share_consent": True}, headers=farmer)
    assert r.status_code == 200 and r.json()["phone"] == "+260971234567" and r.json()["share_consent"]
    withdrawn = client.patch(f"/farmers/{fid}", json={"sms_consent": False}, headers=farmer).json()
    assert withdrawn["phone"] is None                     # withdrawing consent removes the number


def test_officer_cannot_edit_a_self_registered_farmers_profile(client):
    officer = login(client)
    farmer, user = signup(client, "farmer_a", share=True)
    r = client.patch(f"/farmers/{user['farmer_id']}", json={"village": "elsewhere"}, headers=officer)
    assert r.status_code == 403


def test_officer_edits_a_farmer_they_registered(client):
    officer = login(client)
    walk_in = client.post("/farmers", json={"alias": "Walk-in"}, headers=officer).json()
    r = client.patch(f"/farmers/{walk_in['farmer_id']}", json={"phone": "+260971111111", "sms_consent": True},
                     headers=officer)
    assert r.status_code == 200 and r.json()["phone"] == "+260971111111"


def test_moving_a_field_clears_its_map_value(client):
    farmer, _ = signup(client, "farmer_a")
    field = own_field(client, farmer)
    client.get(f"/fields/{field['field_id']}/map-estimate", headers=farmer)
    r = client.patch(f"/fields/{field['field_id']}", json={"name": "River plot", "lat": -15.7, "lon": 28.3,
                                                           "location_source": "manual"}, headers=farmer)
    assert r.status_code == 200 and r.json()["name"] == "River plot" and r.json()["gps_accuracy_m"] is None
    row = backend_db._override.execute("SELECT 1 FROM map_estimates WHERE field_id = ?",
                                       (field["field_id"],)).fetchone()
    assert row is None


def test_bad_gps_rejected_when_moving_a_field(client):
    farmer, _ = signup(client, "farmer_a")
    field = own_field(client, farmer)
    r = client.patch(f"/fields/{field['field_id']}", json={"lat": -15.7, "gps_accuracy_m": 80,
                                                           "location_source": "gps"}, headers=farmer)
    assert r.status_code == 422


def test_farmer_deletes_own_field_with_its_history(client):
    farmer, _ = signup(client, "farmer_a")
    field = own_field(client, farmer)
    client.post(f"/fields/{field['field_id']}/lab-results", json={"ph": 6.0, "ph_method": "water"}, headers=farmer)
    client.post("/advice", json={"field_id": field["field_id"], "crop": "maize"}, headers=farmer)
    assert client.delete(f"/fields/{field['field_id']}", headers=farmer).status_code == 204
    assert client.get(f"/fields/{field['field_id']}", headers=farmer).status_code == 404


def test_admin_manages_accounts(client):
    admin = login(client, "admin")
    r = client.post("/users", json={"username": "mwila.k", "password": "officer-pass-2", "role": "officer",
                                    "full_name": "Mwila K"}, headers=admin)
    assert r.status_code == 201
    new = r.json()
    assert client.post("/auth/login", json={"username": "mwila.k", "password": "officer-pass-2"}).status_code == 200
    client.patch(f"/users/{new['user_id']}", json={"active": False}, headers=admin)
    assert client.post("/auth/login", json={"username": "mwila.k", "password": "officer-pass-2"}).status_code == 403
    assert any(u["username"] == "mwila.k" and not u["active"] for u in client.get("/users", headers=admin).json())


def test_deactivated_account_loses_its_session(client):
    admin = login(client, "admin")
    officer = login(client)
    me = client.get("/auth/me", headers=officer).json()
    client.patch(f"/users/{me['user_id']}", json={"active": False}, headers=admin)
    assert client.get("/farmers", headers=officer).status_code == 401


def test_admin_cannot_lock_themselves_out(client):
    admin = login(client, "admin")
    me = client.get("/auth/me", headers=admin).json()
    assert client.patch(f"/users/{me['user_id']}", json={"active": False}, headers=admin).status_code == 409


def test_only_admin_manages_accounts_and_overview(client):
    officer = login(client)
    farmer, _ = signup(client, "farmer_a")
    for headers in (officer, farmer):
        assert client.get("/users", headers=headers).status_code == 403
        assert client.post("/users", json={"username": "x_user", "password": "whatever-1", "role": "admin",
                                           "full_name": "X"}, headers=headers).status_code == 403
        assert client.get("/overview", headers=headers).status_code == 403
    overview = client.get("/overview", headers=login(client, "admin")).json()
    assert overview["users"]["farmer"] >= 2 and overview["farmers_self_testing"] >= 2


def test_map_shows_only_what_the_user_may_see(client):
    officer = login(client)
    admin = login(client, "admin")
    private, _ = signup(client, "private_farmer", share=False)
    sharing, _ = signup(client, "sharing_farmer", share=True)
    own_field(client, private, "Hidden plot")
    own_field(client, sharing, "Shared plot")
    officer_fields = {p["field"] for p in client.get("/map/points", headers=officer).json()}
    admin_fields = {p["field"] for p in client.get("/map/points", headers=admin).json()}
    assert "Shared plot" in officer_fields and "Hidden plot" not in officer_fields
    assert {"Shared plot", "Hidden plot"} <= admin_fields
    assert {p["field"] for p in client.get("/map/points", headers=private).json()} == {"Hidden plot"}


def test_advice_records_who_asked_and_is_private(client):
    farmer, user = signup(client, "farmer_a")
    other, _ = signup(client, "farmer_b")
    field = own_field(client, farmer)
    client.post(f"/fields/{field['field_id']}/lab-results", json={"ph": 6.0, "ph_method": "water"}, headers=farmer)
    rec = client.post("/advice", json={"field_id": field["field_id"], "crop": "maize"}, headers=farmer).json()
    row = backend_db._override.execute("SELECT user_id FROM recommendations WHERE rec_id = ?",
                                       (rec["rec_id"],)).fetchone()
    assert row["user_id"] == user["user_id"]
    assert client.get(f"/advice/{rec['rec_id']}", headers=other).status_code == 404
    assert client.get("/advice", headers=other).json() == []


def test_unusual_reading_is_checked_before_advice(client):
    farmer, _ = signup(client, "farmer_a")
    field = own_field(client, farmer)
    calibrate(client, farmer)
    first = reading(client, farmer, field["field_id"], 8.9)          # map says 5.4 (test map)
    advice = client.post("/advice", json={"field_id": field["field_id"], "reading_id": first["reading_id"],
                                          "crop": "maize"}, headers=farmer).json()
    assert advice["checks"]["status"] == "check_probe" and "check.retest" in advice["checks"]["reasons"]
    again = reading(client, farmer, field["field_id"], 8.8)           # a repeat agrees: the soil, not the probe
    advice = client.post("/advice", json={"field_id": field["field_id"], "reading_id": again["reading_id"],
                                          "crop": "maize"}, headers=farmer).json()
    assert advice["checks"]["status"] == "confirm_lab" and advice["checks"]["refer_lab"]


def test_old_roles_are_migrated(tmp_path):
    from backend.db import MIGRATIONS_DIR, migrate
    conn = sqlite3.connect(tmp_path / "old.db")
    conn.row_factory = sqlite3.Row
    conn.executescript((MIGRATIONS_DIR / "001_initial.sql").read_text())
    conn.execute("CREATE TABLE schema_migrations (name TEXT PRIMARY KEY, applied_at TEXT)")
    conn.execute("INSERT INTO schema_migrations (name) VALUES ('001_initial.sql')")
    conn.executemany("INSERT INTO users (username, role, password_hash) VALUES (?, ?, 'x')",
                     [("operator", "operator"), ("agronomist", "agronomist"), ("admin", "admin")])
    conn.execute("INSERT INTO farmers (alias) VALUES ('Old farmer')")
    conn.commit()
    migrate(conn)
    roles = dict(conn.execute("SELECT username, role FROM users").fetchall())
    assert roles == {"operator": "officer", "agronomist": "officer", "admin": "admin"}
    farmer = conn.execute("SELECT share_consent, created_by FROM farmers").fetchone()
    assert farmer["share_consent"] == 1 and farmer["created_by"] is not None


def test_field_with_sampling_points_gets_whole_field_advice(client):
    farmer, _ = signup(client, "farmer_a")
    field = own_field(client, farmer, "Shimabala plot")
    calibrate(client, farmer)
    for label, ph in (("S01", 6.1), ("S02", 6.3), ("S04", 7.6)):
        r = client.post("/readings", json={"field_id": field["field_id"], "device_id": "probe-1",
                                           "replicates_ph": [ph, ph, ph], "temp_c": 25, "point_label": label,
                                           "point_lat": -15.679, "point_lon": 28.217}, headers=farmer)
        assert r.json()["point_label"] == label
    points = client.get(f"/fields/{field['field_id']}/history", headers=farmer).json()["points"]
    assert [p["label"] for p in points] == ["S01", "S02", "S04"]
    advice = client.post("/advice", json={"field_id": field["field_id"], "crop": "maize", "whole_field": True},
                         headers=farmer).json()
    whole = advice["whole_field"]
    assert whole["n"] == 3 and whole["median"] == 6.3 and whole["zones"]          # 6.1 to 7.6 differ by 1.5
    assert advice["ph_input"] == 6.3


def test_remeasuring_a_point_replaces_it(client):
    farmer, _ = signup(client, "farmer_a")
    field = own_field(client, farmer)
    calibrate(client, farmer)
    for ph in (6.0, 6.4):
        client.post("/readings", json={"field_id": field["field_id"], "device_id": "probe-1",
                                       "replicates_ph": [ph, ph, ph], "temp_c": 25, "point_label": "S01"}, headers=farmer)
    points = client.get(f"/fields/{field['field_id']}/history", headers=farmer).json()["points"]
    assert len(points) == 1 and points[0]["ph"] == 6.4


def test_whole_field_advice_needs_a_reading(client):
    farmer, _ = signup(client, "farmer_a")
    field = own_field(client, farmer)
    r = client.post("/advice", json={"field_id": field["field_id"], "crop": "maize", "whole_field": True}, headers=farmer)
    assert r.status_code == 422
