"""The probe program on the server's laptop works without a second login (backend.bridge_key)."""

import pytest

from backend import bridge_key
from tests.test_api import client, login, make_field, calibrate  # noqa: F401  (fixtures and helpers)
from tests.test_roles import signup, own_field


@pytest.fixture(autouse=True)
def nobody_acting():
    bridge_key._ACTING.update(user_id=None, since=0.0)
    yield
    bridge_key._ACTING.update(user_id=None, since=0.0)


def key():
    return {"X-Bridge-Key": bridge_key.key_path().read_text().strip()}


def test_the_server_writes_a_key_and_the_probe_can_report_with_it(client):
    assert bridge_key.key_path().exists()
    assert client.post("/devices/probe-1/heartbeat", headers=key()).status_code == 200
    calibrate(client, login(client))
    assert client.post("/devices/probe-1/live", json={"mv": 0.0, "temp_c": 25.0}, headers=key()).status_code == 200


def test_a_wrong_key_is_refused(client):
    assert client.post("/devices/probe-1/heartbeat", headers={"X-Bridge-Key": "guess"}).status_code == 401


def test_the_key_cannot_open_farmer_data(client):
    for path in ("/farmers", "/users", "/referrals", "/map/points"):
        assert client.get(path, headers=key()).status_code == 403


def test_no_reading_without_someone_on_the_live_page(client):
    r = client.post("/readings", json={"field_id": 1, "device_id": "probe-1", "replicates_ph": [6, 6, 6],
                                       "temp_c": 25}, headers=key())
    assert r.status_code == 409


def test_readings_belong_to_whoever_opened_the_live_page(client):
    calibrate(client, login(client))
    farmer, user = signup(client, "sibalo")
    field = own_field(client, farmer)
    assert client.post("/devices/probe-1/active-field", json={"field_id": field["field_id"]}, headers=farmer).status_code == 200
    r = client.post("/readings", json={"field_id": field["field_id"], "device_id": "probe-1",
                                       "replicates_ph": [6.1, 6.1, 6.1], "temp_c": 25}, headers=key())
    assert r.status_code == 201, r.text
    assert r.json()["operator_id"] == user["user_id"]
    # the key acts as that farmer, so it cannot save to someone else's field
    other, _ = signup(client, "other")
    theirs = own_field(client, other)
    r = client.post("/readings", json={"field_id": theirs["field_id"], "device_id": "probe-1",
                                       "replicates_ph": [6.1, 6.1, 6.1], "temp_c": 25}, headers=key())
    assert r.status_code == 404


def test_the_live_page_only_accepts_a_field_you_may_see(client):
    farmer, _ = signup(client, "sibalo")
    other, _ = signup(client, "other")
    theirs = own_field(client, other)
    r = client.post("/devices/probe-1/active-field", json={"field_id": theirs["field_id"]}, headers=farmer)
    assert r.status_code == 404 and bridge_key.acting_user_id() is None


def test_the_bridge_finds_the_key_next_to_the_database(tmp_path, monkeypatch):
    from bridge import bridge
    monkeypatch.delenv("SOILSENSE_BRIDGE_KEY_FILE", raising=False)
    monkeypatch.setenv("SOILSENSE_DB", str(tmp_path / "soilsense.db"))
    assert bridge.local_key() is None
    (tmp_path / "bridge_key.txt").write_text("abc123\n")
    assert bridge.local_key() == "abc123"
