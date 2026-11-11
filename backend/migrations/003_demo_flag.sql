-- Demonstration data (Nov 2026): farmers, users and probes created by
-- `python -m backend.seed_demo` are flagged so that the dashboard can label
-- them and `python -m backend.seed_demo --remove` can delete them. Real data
-- (the retained samples farm, real accounts) is never flagged.
ALTER TABLE users ADD COLUMN is_demo INTEGER NOT NULL DEFAULT 0 CHECK (is_demo IN (0, 1));
ALTER TABLE farmers ADD COLUMN is_demo INTEGER NOT NULL DEFAULT 0 CHECK (is_demo IN (0, 1));
ALTER TABLE devices ADD COLUMN is_demo INTEGER NOT NULL DEFAULT 0 CHECK (is_demo IN (0, 1));
