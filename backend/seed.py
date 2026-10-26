"""Create demo users, one farmer, one field and one device (S1-2).

    python -m backend.seed

Passwords come from SEED_OPERATOR_PASSWORD, SEED_AGRONOMIST_PASSWORD and
SEED_ADMIN_PASSWORD; any that are unset are generated and printed once.
The farmer and field are made up (no real farmer data is stored).
"""

import os
import secrets

from backend.auth import hash_password
from backend.db import connect, migrate
from backend.services.rules_sync import sync_rules

USERS = [("operator", "operator"), ("agronomist", "agronomist"), ("admin", "admin")]


def seed(conn):
    migrate(conn)
    sync_rules(conn)
    created = {}
    with conn:
        for username, role in USERS:
            if conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
                continue
            password = os.environ.get(f"SEED_{role.upper()}_PASSWORD") or secrets.token_urlsafe(9)
            conn.execute("INSERT INTO users (username, role, password_hash) VALUES (?, ?, ?)",
                         (username, role, hash_password(password)))
            created[username] = password
        if not conn.execute("SELECT 1 FROM farmers").fetchone():
            farmer_id = conn.execute(
                "INSERT INTO farmers (alias, preferred_language) VALUES ('Demo farmer A', 'en')").lastrowid
            # Synthetic location near Shimabala; not a real farm.
            conn.execute(
                "INSERT INTO fields (farmer_id, name, lat, lon, gps_accuracy_m, location_source) "
                "VALUES (?, 'Demo field 1', -15.63, 28.24, 8, 'gps')", (farmer_id,))
        conn.execute("INSERT OR IGNORE INTO devices (device_id, label) VALUES ('probe-1', 'Arduino probe 1')")
    return created


if __name__ == "__main__":
    created = seed(connect())
    if created:
        print("Created users (save these passwords now; they are not shown again):")
        for username, password in created.items():
            print(f"  {username:11} {password}")
    else:
        print("Users already exist; nothing new created.")
