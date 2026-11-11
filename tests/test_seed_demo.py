"""Demonstration data (backend.seed_demo): created, labelled, repeatable and removable."""

import json

import pytest

pytest.importorskip("fastapi")

from backend import db as backend_db  # noqa: E402
from backend import seed_demo  # noqa: E402
from backend.routes import fields as fields_routes  # noqa: E402
from backend.seed import seed  # noqa: E402
from engine.map_service import MapEstimate  # noqa: E402


class FakeMap:
    def lookup(self, lat, lon):
        return MapEstimate(6.1, 0.1, 8.0, 8.0, 120.0, "Sandy Clay Loam")


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setenv("SEED_ADMIN_PASSWORD", "admin-pass-1")
    samples = tmp_path / "samples.csv"
    samples.write_text(
        "sample_id,lat,lon,gps_accuracy_m,probe_ph_1,probe_ph_2,probe_ph_3,probe_temp_c,notes\n"
        "S01,-15.679223,28.217512,3,8.55,8.55,8.56,26.1,\n"
        "S02,-15.679295,28.217410,2.5,,,,,\n", encoding="utf-8")
    monkeypatch.setattr(seed_demo, "SAMPLES_CSV", samples)
    connection = backend_db.connect(tmp_path / "demo.db")
    seed(connection)
    fields_routes.set_map_service(FakeMap())
    yield connection
    fields_routes.set_map_service(None)
    backend_db.set_db(None)


def count(conn, sql):
    return conn.execute(sql).fetchone()[0]


def test_demo_fills_every_role_and_labels_it(conn):
    out = seed_demo.demo(conn)
    assert out["created"] >= 20
    assert count(conn, "SELECT COUNT(*) FROM farmers WHERE is_demo = 1") == len(seed_demo.FARMS) + 1   # + Demo farmer A
    assert count(conn, "SELECT COUNT(*) FROM referrals") > 0
    assert count(conn, "SELECT COUNT(*) FROM lab_results") > 0
    assert count(conn, "SELECT COUNT(DISTINCT trust_level) FROM recommendations") >= 2
    # demo readings use demo probes, never the real probe-1
    assert count(conn, "SELECT COUNT(*) FROM calibrations WHERE device_id = 'probe-1'") == 0
    # advice was not spoiled by back-dated calibrations
    results = [json.loads(r[0]) for r in conn.execute("SELECT result FROM recommendations WHERE reading_id IS NOT NULL")]
    assert not any("check.cal_old" in (r.get("checks") or {}).get("reasons", []) for r in results
                   if r["field_id"] in [x[0] for x in conn.execute(
                       "SELECT field_id FROM fields WHERE farmer_id IN (SELECT farmer_id FROM farmers WHERE is_demo = 1)")])
    # the seeding admin does not stay usable
    assert count(conn, "SELECT active FROM users WHERE username = 'demo_seed_admin'") == 0


def test_samples_farm_is_real_and_owned_by_its_login(conn):
    out = seed_demo.demo(conn)
    farmer = conn.execute("SELECT f.* FROM farmers f JOIN users u ON u.user_id = f.user_id "
                          "WHERE u.username = 'samplefarm'").fetchone()
    assert farmer["is_demo"] == 0 and farmer["share_consent"] == 1
    names = {r[0] for r in conn.execute("SELECT name FROM fields WHERE farmer_id = ?", (farmer["farmer_id"],))}
    assert names == {"S01", "S02"}
    assert "samplefarm" in out["passwords"]


def test_running_twice_adds_nothing_and_keeps_passwords(conn):
    seed_demo.demo(conn)
    fields = count(conn, "SELECT COUNT(*) FROM fields")
    second = seed_demo.demo(conn)
    assert second["created"] == 0 and second["passwords"] == {}
    assert count(conn, "SELECT COUNT(*) FROM fields") == fields


def test_remove_deletes_demo_only(conn):
    seed_demo.demo(conn)
    seed_demo.remove(conn)
    assert count(conn, "SELECT COUNT(*) FROM farmers WHERE is_demo = 1") == 0
    assert count(conn, "SELECT COUNT(*) FROM users WHERE is_demo = 1") == 0
    assert count(conn, "SELECT COUNT(*) FROM devices WHERE is_demo = 1") == 0
    assert count(conn, "SELECT COUNT(*) FROM fields WHERE name IN ('S01', 'S02')") == 2
    assert count(conn, "SELECT COUNT(*) FROM users WHERE username = 'samplefarm'") == 1


def test_existing_bridge_samples_are_handed_to_the_samples_login(conn):
    officer = conn.execute("SELECT user_id FROM users WHERE username = 'officer'").fetchone()[0]
    with conn:
        fid = conn.execute("INSERT INTO farmers (alias, created_by) VALUES ('Retained lab samples', ?)", (officer,)).lastrowid
        conn.execute("INSERT INTO fields (farmer_id, name, lat, lon, location_source) VALUES (?, 'S01', -15.67, 28.21, 'manual')", (fid,))
        conn.execute("INSERT INTO fields (farmer_id, name, lat, lon, location_source) VALUES (?, 'S09', -15.67, 28.21, 'manual')", (fid,))
        s09 = conn.execute("SELECT field_id FROM fields WHERE name = 'S09'").fetchone()[0]
        # S01's real reading was saved under S09 by mistake
        conn.execute("INSERT INTO readings (field_id, replicates, quality_status, ph_water) "
                     "VALUES (?, '[8.55, 8.55, 8.56]', 'accepted', 8.55)", (s09,))
    seed_demo.demo(conn)
    owner = conn.execute("SELECT u.username FROM farmers f JOIN users u ON u.user_id = f.user_id "
                         "WHERE f.farmer_id = ?", (fid,)).fetchone()[0]
    assert owner == "samplefarm"
    s01 = conn.execute("SELECT field_id FROM fields WHERE farmer_id = ? AND name = 'S01'", (fid,)).fetchone()[0]
    assert count(conn, f"SELECT COUNT(*) FROM readings WHERE field_id = {s01}") == 1
    assert count(conn, f"SELECT COUNT(*) FROM readings WHERE field_id = {s09}") == 0
