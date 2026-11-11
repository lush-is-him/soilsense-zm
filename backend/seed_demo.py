"""Demonstration data, so the officer and admin screens can be shown working (Nov 2026).

    python -m backend.seed_demo            # add the demo data (safe to run again)
    python -m backend.seed_demo --remove   # delete every demo record again

What it creates
- The REAL samples farm: a farmer account (username `samplefarm`) that owns
  the retained laboratory samples S01-S20 at their SW Maps GPS positions, with
  the probe readings that were actually taken (from docs/evaluation/samples.csv,
  or the readings already in the database). This is not demo data and is never
  flagged or removed.
- DEMO data, flagged `is_demo` and shown with a "demo" badge: two officers, two
  officers' probes, about fifteen made-up farms spread across Kafue District
  with 1-3 fields each. Each demo field's pH starts from the real iSDAsoil value
  at its location (when the map layers are present) plus a realistic probe
  difference, so most agree with the map, a few are acidic enough to need lime,
  and a few are alkaline pockets like the Shimabala samples. Requests to the lab
  and lab results are included, spread over the last three weeks.

Everything goes through the real API, so trust levels, plausibility checks
and advice are produced by the engine exactly as for a real farmer.
"""

import csv
import os
import random
import secrets
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from backend import config
from backend import db as backend_db
from backend.auth import create_token, hash_password
from backend.seed import seed
from backend.services.probe import theoretical_slope_mv

ROOT = Path(__file__).resolve().parent.parent
SAMPLES_CSV = ROOT / "docs" / "evaluation" / "samples.csv"
SAMPLE_FARM_ALIASES = ("Shimabala sample farm", "Retained lab samples")
SAMPLE_FARM_USER = "samplefarm"

# Area centres in Kafue District (approximate) and how their demo soils behave.
AREAS = [
    ("Shimabala", -15.665, 28.225, "alkaline"),
    ("Chilanga", -15.565, 28.270, "normal"),
    ("Kafue town", -15.770, 28.180, "normal"),
    ("Nangongwe", -15.720, 28.120, "acid"),
    ("Chikupi", -15.900, 28.160, "normal"),
    ("Kafue Flats edge", -15.830, 28.000, "acid"),
]
FARMS = [  # alias, area, own account?, shares?, number of fields
    ("Phiri family farm", "Shimabala", True, True, 2),
    ("Mwanza garden plots", "Shimabala", False, True, 1),
    ("Banda family farm", "Chilanga", True, True, 3),
    ("Tembo smallholding", "Chilanga", True, True, 1),
    ("Zulu co-op plot", "Chilanga", False, True, 2),
    ("Mulenga farm", "Kafue town", True, True, 2),
    ("Sakala family farm", "Kafue town", True, False, 1),
    ("Chanda maize plot", "Nangongwe", True, True, 2),
    ("Mbewe family farm", "Nangongwe", False, True, 2),
    ("Lungu smallholding", "Nangongwe", True, True, 1),
    ("Hamoonga farm", "Chikupi", True, True, 2),
    ("Mweemba family farm", "Chikupi", False, True, 1),
    ("Hachintu plots", "Kafue Flats edge", True, True, 2),
    ("Siamuntu farm", "Kafue Flats edge", True, True, 1),
    ("Muleya garden", "Kafue town", True, True, 1),
]
FIELD_NAMES = ["Main field", "Plot by the road", "River plot", "Back field", "Garden"]
CROPS = ["maize", "maize", "maize", "soybean", "groundnut", "sunflower"]
OFFICERS = [("demo_officer_chilanga", "Chilanga camp officer (demo)"),
            ("demo_officer_zari", "ZARI Mount Makulu lab officer (demo)")]


def _client(conn):
    from fastapi.testclient import TestClient
    from backend.main import app
    backend_db.set_db(conn)
    return TestClient(app)


def _as(conn, username):
    """Act as this user through the API (a signed token; no password needed)."""
    row = conn.execute("SELECT user_id, role FROM users WHERE username = ?", (username,)).fetchone()
    return {"Authorization": f"Bearer {create_token(row['user_id'], row['role'], hours=2)}"}


def _user(conn, username, full_name, role, demo, password=None):
    """Create the account if missing. Returns its password if it was created now, else None
    (an existing account keeps the password its owner chose)."""
    if conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
        with conn:
            conn.execute("UPDATE users SET active = 1 WHERE username = ?", (username,))
        return None
    password = password or secrets.token_urlsafe(10)
    with conn:
        conn.execute("INSERT INTO users (username, full_name, role, password_hash, is_demo) VALUES (?, ?, ?, ?, ?)",
                     (username, full_name, role, hash_password(password), int(demo)))
    return password


def _calibrate(client, headers, device, temp=25.5, slope_pct=None):
    slope_pct = slope_pct or random.uniform(97, 103.5)
    slope = theoretical_slope_mv(temp) * slope_pct / 100
    return client.post(f"/devices/{device}/calibrations",
                       json={"mv_ph7": 0.0, "mv_ph4": round(3 * slope, 1), "temp_c": temp}, headers=headers).json()


def _mv_for(ph, temp, slope_pct):
    return round(-(ph - 7.0) * theoretical_slope_mv(temp) * slope_pct / 100, 1)


def _backdate(conn, table, key, value, when):
    column = {"readings": "ts", "recommendations": "created_at", "referrals": "created_at",
              "calibrations": "date", "field_checks": "ts"}[table]
    with conn:
        conn.execute(f"UPDATE {table} SET {column} = ? WHERE {key} = ?", (when.strftime("%Y-%m-%d %H:%M:%S"), value))


# ----- the real samples farm ---------------------------------------------------

def _move_misfiled_readings(conn, farmer_id, rows):
    """A reading saved under the wrong sample code (S06 measured as S09) and corrected in
    samples.csv with scripts/move_sample.py: move it to the right field in the database too."""
    by_name = {r["name"]: r["field_id"] for r in conn.execute("SELECT name, field_id FROM fields WHERE farmer_id = ?", (farmer_id,))}
    csv_ph = {r["sample_id"]: [round(float(r[f"probe_ph_{i}"]), 2) for i in (1, 2, 3)]
              for r in rows if all(r.get(f"probe_ph_{i}") for i in (1, 2, 3))}
    for name, field_id in by_name.items():
        if name in csv_ph:
            continue
        for reading in conn.execute("SELECT reading_id, replicates FROM readings WHERE field_id = ?", (field_id,)).fetchall():
            import json
            values = [round(v, 2) for v in json.loads(reading["replicates"] or "[]")]
            target = next((n for n, ph in csv_ph.items() if sorted(ph) == sorted(values) and n in by_name), None)
            if target and not conn.execute("SELECT 1 FROM readings WHERE field_id = ?", (by_name[target],)).fetchone():
                with conn:
                    for table in ("readings", "recommendations"):
                        conn.execute(f"UPDATE {table} SET field_id = ? WHERE field_id = ? AND "
                                     f"{'reading_id' if table == 'readings' else 'reading_id'} = ?",
                                     (by_name[target], field_id, reading["reading_id"]))


def sample_farm(conn, client, password):
    """The farmer account that owns the retained laboratory samples. Real data."""
    created = _user(conn, SAMPLE_FARM_USER, "Shimabala sample farm", "farmer", demo=False, password=password)
    user_id = conn.execute("SELECT user_id FROM users WHERE username = ?", (SAMPLE_FARM_USER,)).fetchone()[0]
    farmer = conn.execute("SELECT farmer_id FROM farmers WHERE user_id = ?", (user_id,)).fetchone()
    if farmer is None:
        existing = conn.execute(
            f"SELECT farmer_id FROM farmers WHERE alias IN ({','.join('?' * len(SAMPLE_FARM_ALIASES))}) "
            "AND user_id IS NULL ORDER BY farmer_id LIMIT 1", SAMPLE_FARM_ALIASES).fetchone()
        with conn:
            if existing:                    # the bridge already registered the samples: hand them to this login
                conn.execute("UPDATE farmers SET user_id = ?, alias = 'Shimabala sample farm', village = 'Shimabala', "
                             "share_consent = 1 WHERE farmer_id = ?", (user_id, existing[0]))
            else:
                conn.execute("INSERT INTO farmers (alias, village, share_consent, user_id, created_by) "
                             "VALUES ('Shimabala sample farm', 'Shimabala', 1, ?, ?)", (user_id, user_id))
        farmer = conn.execute("SELECT farmer_id FROM farmers WHERE user_id = ?", (user_id,)).fetchone()
    farmer_id = farmer[0]
    headers = _as(conn, SAMPLE_FARM_USER)
    rows = list(csv.DictReader(open(SAMPLES_CSV, newline="", encoding="utf-8"))) if SAMPLES_CSV.exists() else []
    _move_misfiled_readings(conn, farmer_id, rows)
    fields = {f["name"]: f for f in client.get(f"/farmers/{farmer_id}", headers=headers).json()["fields"]}
    for row in rows:
        if not (row.get("lat") and row.get("lon")):
            continue
        name = row["sample_id"]
        if name not in fields:
            accuracy = float(row["gps_accuracy_m"]) if row.get("gps_accuracy_m") else None
            fields[name] = client.post("/fields", json={
                "name": name, "lat": float(row["lat"]), "lon": float(row["lon"]), "gps_accuracy_m": accuracy,
                "location_source": "gps" if accuracy is not None and accuracy <= 30 else "manual"}, headers=headers).json()
        field = fields[name]
        has_reading = conn.execute("SELECT 1 FROM readings WHERE field_id = ?", (field["field_id"],)).fetchone()
        reps = [row.get(f"probe_ph_{i}") for i in (1, 2, 3)]
        if not has_reading and all(reps):
            # The real readings from samples.csv (taken with probe-1 on 5 Nov 2026).
            temp = float(row.get("probe_temp_c") or 25.0)
            reading = client.post("/readings", json={"field_id": field["field_id"], "device_id": "probe-1",
                                                     "replicates_ph": [float(v) for v in reps], "temp_c": temp},
                                  headers=headers).json()
            if reading.get("quality_status") == "accepted":
                client.post("/advice", json={"field_id": field["field_id"], "reading_id": reading["reading_id"],
                                             "crop": "maize"}, headers=headers)
    return created


# ----- demo farms ---------------------------------------------------------------------

def demo(conn, rng=None):
    rng = rng or random.Random(2026)
    random.seed(2026)
    client = _client(conn)
    _user(conn, "demo_seed_admin", "Demo seeding (temporary)", "admin", demo=True)
    admin = _as(conn, "demo_seed_admin")
    officers, passwords = {}, {}
    for username, name in OFFICERS:
        pw = _user(conn, username, name, "officer", demo=True,
                   password=os.environ.get("SEED_DEMO_OFFICER_PASSWORD") or "demo-officer-1")
        if pw:
            passwords[username] = pw
        officers[username] = _as(conn, username)
    for device, label in (("probe-2-demo", "Chilanga camp probe (demo)"), ("probe-3-demo", "ZARI lab probe (demo)")):
        with conn:
            conn.execute("INSERT OR IGNORE INTO devices (device_id, label, is_demo) VALUES (?, ?, 1)", (device, label))

    pw = sample_farm(conn, client, os.environ.get("SEED_SAMPLEFARM_PASSWORD") or "samplefarm-1")
    if pw:
        passwords[SAMPLE_FARM_USER] = pw

    if conn.execute("SELECT 1 FROM farmers WHERE is_demo = 1 AND alias != 'Demo farmer A'").fetchone():
        _cleanup_seed_admin(conn)
        return {"passwords": passwords, "created": 0}

    now = datetime.now(timezone.utc)
    areas = {a[0]: a for a in AREAS}
    created = 0
    chilanga, zari = officers["demo_officer_chilanga"], officers["demo_officer_zari"]
    for index, (alias, area, own_account, shares, n_fields) in enumerate(FARMS):
        _, lat0, lon0, behaviour = areas[area]
        if own_account:
            username = "demo_" + alias.split()[0].lower()
            _user(conn, username, alias, "farmer", demo=True)
            user_id = conn.execute("SELECT user_id FROM users WHERE username = ?", (username,)).fetchone()[0]
            with conn:
                conn.execute("INSERT INTO farmers (alias, village, share_consent, user_id, created_by, is_demo, "
                             "preferred_language) VALUES (?, ?, ?, ?, ?, 1, ?)",
                             (alias, area, int(shares), user_id, user_id, rng.choice(["en", "en", "toi"])))
            headers = _as(conn, username)
            farmer_id = conn.execute("SELECT farmer_id FROM farmers WHERE user_id = ?", (user_id,)).fetchone()[0]
        else:
            headers = chilanga
            farmer = client.post("/farmers", json={"alias": alias, "village": area, "share_consent": shares,
                                                   "preferred_language": "toi"}, headers=chilanga).json()
            farmer_id = farmer["farmer_id"]
            with conn:
                conn.execute("UPDATE farmers SET is_demo = 1 WHERE farmer_id = ?", (farmer_id,))
        device = "probe-1" if own_account else "probe-2-demo"
        for k in range(n_fields):
            lat = round(lat0 + rng.uniform(-0.03, 0.03), 6)
            lon = round(lon0 + rng.uniform(-0.03, 0.03), 6)
            field = client.post("/fields", json={"farmer_id": farmer_id, "name": FIELD_NAMES[k], "lat": lat, "lon": lon,
                                                 "gps_accuracy_m": rng.choice([3, 4, 5, 6, 8]),
                                                 "location_source": "gps"}, headers=headers).json()
            map_est = client.get(f"/fields/{field['field_id']}/map-estimate", headers=headers)
            map_ph = map_est.json()["ph_mean"] if map_est.status_code == 200 else 6.1
            if behaviour == "alkaline" and rng.random() < 0.7:
                ph = map_ph + rng.uniform(1.0, 2.0)
            elif behaviour == "acid" and rng.random() < 0.6:
                ph = rng.uniform(4.7, 5.4)
            else:
                ph = map_ph + rng.uniform(-0.45, 0.45)
            ph = round(min(max(ph, 4.4), 8.6), 2)
            when = now - timedelta(days=rng.uniform(1, 21), hours=rng.uniform(0, 8))
            temp = round(rng.uniform(24.0, 28.0), 1)
            # a demo calibration of the probe used, on the same morning, then the reading
            dev = "probe-2-demo" if device == "probe-1" else device   # never touch the real probe's calibration
            slope_pct = rng.uniform(97, 103.5)
            cal = _calibrate(client, admin, dev, temp=temp, slope_pct=slope_pct)
            reps = [_mv_for(ph + d, temp, slope_pct) for d in (0.0, rng.uniform(-0.03, 0.03), rng.uniform(-0.03, 0.03))]
            reading = client.post("/readings", json={"field_id": field["field_id"], "device_id": dev,
                                                     "replicates_mv": reps, "temp_c": temp}, headers=headers).json()
            if rng.random() < 0.5:
                check = client.post(f"/fields/{field['field_id']}/checks",
                                    json={"texture_by_feel": rng.choice(["loamy", "loamy", "clay", "sandy"]),
                                          "manure_available": rng.random() < 0.5}, headers=headers).json()
                _backdate(conn, "field_checks", "check_id", check["check_id"], when)
            crop = rng.choice(CROPS)
            advice = client.post("/advice", json={"field_id": field["field_id"], "reading_id": reading["reading_id"],
                                                  "crop": crop, "as_of_date": when.date().isoformat(),
                                                  "budget_band": rng.choice(["low", "medium"])}, headers=headers).json()
            # the calibration, reading and advice happened together, `when`
            _backdate(conn, "calibrations", "calibration_id", cal["calibration_id"], when - timedelta(hours=1))
            _backdate(conn, "readings", "reading_id", reading["reading_id"], when)
            _backdate(conn, "recommendations", "rec_id", advice["rec_id"], when + timedelta(minutes=3))
            unusual = advice.get("checks", {}).get("status") in ("check_probe", "confirm_lab")
            # Requests: most unusual readings ask for a lab test; some farmers ask for a visit.
            if (unusual and rng.random() < 0.9) or rng.random() < 0.25:
                kind = "lab" if unusual or rng.random() < 0.6 else "visit"
                ref = client.post("/referrals", json={"field_id": field["field_id"], "kind": kind,
                                                      "reading_id": reading["reading_id"],
                                                      "reason": "Confirm this reading with a lab test" if kind == "lab"
                                                      else "Please come and test my soil"}, headers=headers).json()
                ref_when = when + timedelta(hours=2)
                _backdate(conn, "referrals", "referral_id", ref["referral_id"], ref_when)
                fate = rng.random()
                if kind == "lab" and fate < 0.4 and ref_when < now - timedelta(days=5):
                    lab_ph = round(ph + rng.uniform(-0.35, 0.35), 2)
                    client.post(f"/fields/{field['field_id']}/lab-results",
                                json={"ph": lab_ph, "ph_method": "water", "lab_name": "ZARI Mount Makulu",
                                      "texture": map_est.json().get("texture") if map_est.status_code == 200 else None,
                                      "referral_id": ref["referral_id"], "date": (ref_when + timedelta(days=4)).date().isoformat()},
                                headers=zari)
                    high = client.post("/advice", json={"field_id": field["field_id"], "crop": crop}, headers=headers).json()
                    _backdate(conn, "recommendations", "rec_id", high["rec_id"], ref_when + timedelta(days=4))
                elif fate < 0.55:
                    client.patch(f"/referrals/{ref['referral_id']}", json={"status": "in_progress"}, headers=chilanga)
            created += 1
    _cleanup_seed_admin(conn)
    return {"passwords": passwords, "created": created}


def _cleanup_seed_admin(conn):
    with conn:
        conn.execute("UPDATE users SET active = 0 WHERE username = 'demo_seed_admin'")
        # the made-up farmer from backend.seed is demo data too
        conn.execute("UPDATE farmers SET is_demo = 1 WHERE alias = 'Demo farmer A'")


def remove(conn):
    """Delete every demo farmer, field, reading, request, advice, account and probe."""
    with conn:
        fields = [r[0] for r in conn.execute(
            "SELECT field_id FROM fields WHERE farmer_id IN (SELECT farmer_id FROM farmers WHERE is_demo = 1)")]
        marks = ",".join("?" * len(fields)) or "NULL"
        conn.execute(f"DELETE FROM recommendation_rules WHERE rec_id IN (SELECT rec_id FROM recommendations WHERE field_id IN ({marks}))", fields)
        conn.execute(f"DELETE FROM sms_messages WHERE rec_id IN (SELECT rec_id FROM recommendations WHERE field_id IN ({marks}))", fields)
        for table in ("recommendations", "lab_results", "referrals", "readings", "field_checks", "map_estimates"):
            conn.execute(f"DELETE FROM {table} WHERE field_id IN ({marks})", fields)
        conn.execute(f"DELETE FROM fields WHERE field_id IN ({marks})", fields)
        conn.execute("DELETE FROM farmers WHERE is_demo = 1")
        demo_devices = [r[0] for r in conn.execute("SELECT device_id FROM devices WHERE is_demo = 1")]
        dmarks = ",".join("?" * len(demo_devices)) or "NULL"
        conn.execute(f"UPDATE readings SET device_id = NULL WHERE device_id IN ({dmarks})", demo_devices)
        conn.execute(f"DELETE FROM calibrations WHERE device_id IN ({dmarks})", demo_devices)
        conn.execute(f"DELETE FROM devices WHERE device_id IN ({dmarks})", demo_devices)
        demo_users = [r[0] for r in conn.execute("SELECT user_id FROM users WHERE is_demo = 1")]
        umarks = ",".join("?" * len(demo_users)) or "NULL"
        for table, column in (("readings", "operator_id"), ("recommendations", "user_id"), ("referrals", "created_by"),
                              ("referrals", "handled_by"), ("lab_results", "entered_by"), ("farmers", "created_by")):
            conn.execute(f"UPDATE {table} SET {column} = NULL WHERE {column} IN ({umarks})", demo_users)
        conn.execute("DELETE FROM users WHERE is_demo = 1")
    return len(fields)


if __name__ == "__main__":
    conn = backend_db.connect()
    seed(conn)
    if "--remove" in sys.argv:
        print(f"Removed the demo data ({remove(conn)} demo fields). Real data was not touched.")
    else:
        out = demo(conn)
        print("Demo data ready." if out["created"] else "Demo farms already exist; checked the samples farm.")
        print(f"  Your samples farm:  username {SAMPLE_FARM_USER}")
        print("  Demo officers:      username demo_officer_chilanga or demo_officer_zari")
        print("  Admin:              your existing admin account")
        for username, password in out["passwords"].items():
            print(f"  New password for {username}: {password}   (save it; change with python -m backend.set_password {username})")
        print("  Remove the demo data any time: python -m backend.seed_demo --remove")
