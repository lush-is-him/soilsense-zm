"""The probe program (bridge) on the laptop, without a second login.

The bridge runs on the same laptop as the server (START_DEMO starts both). When the
server starts it writes a random key into a file next to the database; the bridge
reads that file and sends the key instead of a username and password. Anyone who can
read the file is already sitting at the laptop, and the key is accepted only from the
laptop itself (not from phones on the Wi-Fi).

The key does not make the bridge a user. It may:
- use the probe's own endpoints (/devices/...): heartbeat, live value, calibration;
- save a reading, acting for the person who opened the Live page in the dashboard,
  so the reading is theirs and they can only save it to a field they may see.
"""

import os
import secrets
import time
from pathlib import Path

from backend import config

HEADER = "X-Bridge-Key"
ACTING_HOURS = 12                     # how long a Live page counts as open
_ACTING = {"user_id": None, "since": 0.0}


def key_path():
    return Path(os.environ.get("SOILSENSE_BRIDGE_KEY_FILE", config.DB_PATH.parent / "bridge_key.txt"))


def ensure_key():
    path = key_path()
    if not path.exists() or not path.read_text().strip():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(secrets.token_hex(32))
    return path.read_text().strip()


def matches(value):
    path = key_path()
    if not value or not path.exists():
        return False
    return secrets.compare_digest(value.strip(), path.read_text().strip())


def set_acting(user_id):
    """Called when someone opens the Live page: the probe's readings are theirs."""
    _ACTING.update(user_id=user_id, since=time.monotonic())


def acting_user_id():
    if _ACTING["user_id"] and time.monotonic() - _ACTING["since"] < ACTING_HOURS * 3600:
        return _ACTING["user_id"]
    return None


def is_local(request):
    host = request.client.host if request.client else ""
    return host in ("127.0.0.1", "::1", "localhost", "testclient")
