-- SoilSense ZM schema v1 (spec section 3)

CREATE TABLE users (
    user_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    role          TEXT NOT NULL CHECK (role IN ('operator', 'agronomist', 'admin')),
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE farmers (
    farmer_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    alias              TEXT NOT NULL,
    preferred_language TEXT NOT NULL DEFAULT 'en' CHECK (preferred_language IN ('en', 'ny', 'toi')),
    phone              TEXT,                    -- only with consent; deleted after demos (NFR5)
    sms_consent        INTEGER NOT NULL DEFAULT 0 CHECK (sms_consent IN (0, 1)),
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (phone IS NULL OR sms_consent = 1)
);

CREATE TABLE fields (
    field_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    farmer_id       INTEGER NOT NULL REFERENCES farmers(farmer_id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    lat             REAL NOT NULL CHECK (lat BETWEEN -90 AND 90),
    lon             REAL NOT NULL CHECK (lon BETWEEN -180 AND 180),
    gps_accuracy_m  REAL,
    location_source TEXT NOT NULL CHECK (location_source IN ('gps', 'manual')),
    area_lima       REAL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE devices (
    device_id TEXT PRIMARY KEY,
    label     TEXT NOT NULL
);

CREATE TABLE calibrations (
    calibration_id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id      TEXT NOT NULL REFERENCES devices(device_id),
    date           TEXT NOT NULL DEFAULT (datetime('now')),
    offset_mv      REAL NOT NULL,               -- electrode mV in the pH 7.00 buffer
    slope_pct      REAL NOT NULL,               -- % of theoretical Nernst slope
    temp_c         REAL NOT NULL,
    accepted       INTEGER NOT NULL CHECK (accepted IN (0, 1)),
    reasons        TEXT                         -- JSON list
);

CREATE TABLE readings (
    reading_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    field_id        INTEGER NOT NULL REFERENCES fields(field_id) ON DELETE CASCADE,
    device_id       TEXT REFERENCES devices(device_id),
    operator_id     INTEGER REFERENCES users(user_id),
    calibration_id  INTEGER REFERENCES calibrations(calibration_id),
    ph_water        REAL,                       -- mean of replicates; NULL if rejected
    ph_method       TEXT NOT NULL DEFAULT 'water' CHECK (ph_method = 'water'),
    replicates      TEXT NOT NULL,              -- JSON list of pH values
    replicates_mv   TEXT,                       -- JSON list of raw mV, when from the probe
    moisture        REAL,
    temp_c          REAL,
    quality_status  TEXT NOT NULL CHECK (quality_status IN ('accepted', 'rejected')),
    quality_reasons TEXT,                       -- JSON list
    ts              TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE map_estimates (
    estimate_id INTEGER PRIMARY KEY AUTOINCREMENT,
    field_id    INTEGER NOT NULL UNIQUE REFERENCES fields(field_id) ON DELETE CASCADE,
    ph_mean     REAL NOT NULL,
    ph_sd       REAL NOT NULL,
    ph_method   TEXT NOT NULL DEFAULT 'water',
    oc          REAL,
    p           REAL,
    k           REAL,
    texture     TEXT,
    depth_cm    TEXT NOT NULL DEFAULT '0-20'
);

CREATE TABLE lab_results (
    lab_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    field_id         INTEGER NOT NULL REFERENCES fields(field_id) ON DELETE CASCADE,
    ph               REAL NOT NULL,
    ph_method        TEXT NOT NULL CHECK (ph_method IN ('water', 'cacl2')),
    soil_water_ratio TEXT,
    oc               REAL,
    p                REAL,
    k                REAL,
    texture          TEXT,
    lab_name         TEXT,
    date             TEXT
);

CREATE TABLE field_checks (
    check_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    field_id          INTEGER NOT NULL REFERENCES fields(field_id) ON DELETE CASCADE,
    texture_by_feel   TEXT CHECK (texture_by_feel IN ('sandy', 'loamy', 'clay')),
    colour            TEXT,
    waterlogging      INTEGER CHECK (waterlogging IN (0, 1)),
    previous_crop     TEXT,
    manure_available  INTEGER CHECK (manure_available IN (0, 1)),
    ts                TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE recommendations (
    rec_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    reading_id       INTEGER REFERENCES readings(reading_id),
    field_id         INTEGER NOT NULL REFERENCES fields(field_id) ON DELETE CASCADE,
    trust_level      TEXT NOT NULL,
    crop             TEXT NOT NULL,
    budget_band      TEXT,
    water            TEXT,
    plan_a           TEXT,                      -- JSON
    plan_b           TEXT,                      -- JSON
    plan_c           TEXT,                      -- JSON
    result           TEXT NOT NULL,             -- full engine output, JSON
    language         TEXT NOT NULL DEFAULT 'en',
    as_of_date       TEXT NOT NULL,
    method_sensitive INTEGER NOT NULL DEFAULT 0,
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Mirror of rules/*.yaml for audit; the YAML is the source of truth.
CREATE TABLE rules (
    rule_id        TEXT PRIMARY KEY,
    version        INTEGER NOT NULL DEFAULT 1,
    content_hash   TEXT NOT NULL,
    domain         TEXT NOT NULL,
    data           TEXT NOT NULL,               -- JSON (replaces condition/action, spec 3)
    status         TEXT NOT NULL,
    source_type    TEXT NOT NULL,
    source_doc     TEXT,
    reviewer_alias TEXT,
    ph_method      TEXT,
    notes          TEXT,
    updated_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE recommendation_rules (
    rec_id       INTEGER NOT NULL REFERENCES recommendations(rec_id) ON DELETE CASCADE,
    rule_id      TEXT NOT NULL REFERENCES rules(rule_id),
    rule_version INTEGER NOT NULL,
    PRIMARY KEY (rec_id, rule_id)
);

CREATE TABLE sms_messages (
    sms_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    rec_id  INTEGER NOT NULL REFERENCES recommendations(rec_id) ON DELETE CASCADE,
    status  TEXT NOT NULL,
    ts      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_fields_farmer ON fields(farmer_id);
CREATE INDEX idx_readings_field ON readings(field_id);
CREATE INDEX idx_recommendations_field ON recommendations(field_id);
