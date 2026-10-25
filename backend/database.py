# ============================================================
# SoilSense ZM — Backend
# database.py — SQLite database setup
# ============================================================

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "soilsense.db")


def get_connection():
    """Get a SQLite database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS farmers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL UNIQUE,
            location TEXT NOT NULL,
            district TEXT DEFAULT 'Kafue',
            farm_size_hectares REAL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            farmer_id INTEGER,
            pH REAL NOT NULL,
            moisture REAL NOT NULL,
            temperature REAL NOT NULL,
            nitrogen REAL,
            phosphorus REAL,
            organic_carbon REAL,
            prediction TEXT NOT NULL,
            confidence REAL NOT NULL,
            advisory TEXT,
            latitude REAL,
            longitude REAL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (farmer_id) REFERENCES farmers(id)
        )
    """)

    conn.commit()
    conn.close()
    print("   ✅ Database initialized: soilsense.db")


# Initialize on import
init_db()
