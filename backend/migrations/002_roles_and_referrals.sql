-- Self-testing model (Nov 2026): personal accounts with three roles, farmer
-- profiles that a farmer can own, sharing consent, and referrals to the lab.
--
-- Roles: farmer (tests their own fields), officer (extension or lab staff:
-- sees shared tests, handles referrals, can test for a farmer), admin.
-- Old roles: operator and agronomist become officer.

PRAGMA foreign_keys = OFF;

CREATE TABLE users_new (
    user_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    full_name     TEXT,
    role          TEXT NOT NULL CHECK (role IN ('farmer', 'officer', 'admin')),
    password_hash TEXT NOT NULL,
    active        INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
INSERT INTO users_new (user_id, username, role, password_hash, created_at)
    SELECT user_id, username, CASE role WHEN 'admin' THEN 'admin' ELSE 'officer' END,
           password_hash, created_at
    FROM users;
DROP TABLE users;
ALTER TABLE users_new RENAME TO users;

-- A farmer profile may belong to a farmer's own login (user_id), or be kept
-- by an officer for a farmer without a smartphone (created_by).
ALTER TABLE farmers ADD COLUMN user_id INTEGER REFERENCES users(user_id);
ALTER TABLE farmers ADD COLUMN village TEXT;
ALTER TABLE farmers ADD COLUMN share_consent INTEGER NOT NULL DEFAULT 0 CHECK (share_consent IN (0, 1));
ALTER TABLE farmers ADD COLUMN created_by INTEGER REFERENCES users(user_id);
CREATE UNIQUE INDEX farmers_user_id ON farmers(user_id) WHERE user_id IS NOT NULL;

-- Farmers registered before this migration were registered by the project's
-- own operator for the study: keep them visible to officers.
UPDATE farmers SET share_consent = 1,
                   created_by = (SELECT MIN(user_id) FROM users WHERE role = 'officer')
WHERE created_by IS NULL;

-- Who asked for each piece of advice.
ALTER TABLE recommendations ADD COLUMN user_id INTEGER REFERENCES users(user_id);

-- A request for a lab test, or for an officer to visit and test.
CREATE TABLE referrals (
    referral_id INTEGER PRIMARY KEY AUTOINCREMENT,
    field_id    INTEGER NOT NULL REFERENCES fields(field_id) ON DELETE CASCADE,
    reading_id  INTEGER REFERENCES readings(reading_id),
    kind        TEXT NOT NULL CHECK (kind IN ('lab', 'visit')),
    reason      TEXT,
    status      TEXT NOT NULL DEFAULT 'open'
                CHECK (status IN ('open', 'in_progress', 'done', 'cancelled')),
    note        TEXT,
    created_by  INTEGER REFERENCES users(user_id),
    handled_by  INTEGER REFERENCES users(user_id),
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT
);
CREATE INDEX referrals_status ON referrals(status);

ALTER TABLE lab_results ADD COLUMN referral_id INTEGER REFERENCES referrals(referral_id);
ALTER TABLE lab_results ADD COLUMN entered_by INTEGER REFERENCES users(user_id);

PRAGMA foreign_keys = ON;
