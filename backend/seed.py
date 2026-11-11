"""Create the starting accounts, one demo farmer with a field, and the probe (S1-2).

    python -m backend.seed

Accounts: admin (role admin), officer (an extension or lab officer) and
farmer (a self-testing farmer, linked to the demo farmer profile). Passwords
come from SEED_ADMIN_PASSWORD, SEED_OFFICER_PASSWORD and SEED_FARMER_PASSWORD;
any that are unset are generated and printed once. The admin then creates
real, named accounts for officers from the dashboard, and farmers sign up
themselves. The demo farmer and field are made up (no real farmer data).
"""

import os
import secrets

from backend.auth import hash_password
from backend.db import connect, migrate
from backend.services.rules_sync import sync_rules

USERS = [("admin", "admin", "Administrator"),
         ("officer", "officer", "Demo extension officer"),
         ("farmer", "farmer", "Demo farmer A")]


def _password(role):
    legacy = {"officer": "SEED_OPERATOR_PASSWORD"}      # before Nov 2026 the officer was "operator"
    return (os.environ.get(f"SEED_{role.upper()}_PASSWORD")
            or os.environ.get(legacy.get(role, ""), "") or secrets.token_urlsafe(9))


def seed(conn):
    migrate(conn)
    sync_rules(conn)
    created = {}
    with conn:
        for username, role, full_name in USERS:
            if conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
                continue
            password = _password(role)
            conn.execute("INSERT INTO users (username, full_name, role, password_hash) VALUES (?, ?, ?, ?)",
                         (username, full_name, role, hash_password(password)))
            created[username] = password
        officer = conn.execute("SELECT user_id FROM users WHERE username = 'officer'").fetchone()
        farmer_user = conn.execute("SELECT user_id FROM users WHERE username = 'farmer'").fetchone()
        if not conn.execute("SELECT 1 FROM farmers").fetchone():
            farmer_id = conn.execute(
                "INSERT INTO farmers (alias, preferred_language, user_id, village, share_consent, created_by) "
                "VALUES ('Demo farmer A', 'en', ?, 'Shimabala', 1, ?)",
                (farmer_user["user_id"] if farmer_user else None,
                 officer["user_id"] if officer else None)).lastrowid
            # Synthetic location near Shimabala; not a real farm.
            conn.execute(
                "INSERT INTO fields (farmer_id, name, lat, lon, gps_accuracy_m, location_source) "
                "VALUES (?, 'Demo field 1', -15.63, 28.24, 8, 'gps')", (farmer_id,))
        elif farmer_user and not conn.execute("SELECT 1 FROM farmers WHERE user_id = ?",
                                              (farmer_user["user_id"],)).fetchone():
            # an existing database: give the new farmer login the demo farmer profile, if it has no owner
            conn.execute("UPDATE farmers SET user_id = ? WHERE alias = 'Demo farmer A' AND user_id IS NULL",
                         (farmer_user["user_id"],))
        conn.execute("INSERT OR IGNORE INTO devices (device_id, label) VALUES ('probe-1', 'Arduino probe 1')")
    return created


if __name__ == "__main__":
    created = seed(connect())
    if created:
        print("Created accounts (save these passwords now; they are not shown again):")
        for username, password in created.items():
            print(f"  {username:8} {password}")
    else:
        print("Accounts already exist; nothing new created.")
