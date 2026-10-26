"""Backend settings, read from environment variables (spec 0 rule 7).

Never put real secrets in this file. Copy .env.example to .env (ignored by
git) or set the variables in your shell.
"""

import os
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DB_PATH = Path(os.environ.get("SOILSENSE_DB", ROOT / "data" / "soilsense.db"))
MAP_DATA_DIR = Path(os.environ.get("SOILSENSE_MAP_DIR", ROOT / "data" / "isdasoil"))
TOKEN_HOURS = float(os.environ.get("SOILSENSE_TOKEN_HOURS", "12"))

# Signs login tokens. Without it a random key is used, so tokens stop
# working when the server restarts (fine for development).
SECRET_KEY = os.environ.get("SOILSENSE_SECRET_KEY") or secrets.token_hex(32)

AT_USERNAME = os.environ.get("AT_USERNAME", "sandbox")
AT_API_KEY = os.environ.get("AT_API_KEY", "")
AT_SENDER_ID = os.environ.get("AT_SENDER_ID", "")
