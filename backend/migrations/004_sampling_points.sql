-- Sampling points (Nov 2026): a field can hold several separately measured
-- samples, each with a label (S01...) and its own GPS position. Advice can then
-- be given for the whole field from the median of its points, and the spread
-- of the points shows when parts of the field should be treated separately.
ALTER TABLE readings ADD COLUMN point_label TEXT;
ALTER TABLE readings ADD COLUMN point_lat REAL;
ALTER TABLE readings ADD COLUMN point_lon REAL;
ALTER TABLE recommendations ADD COLUMN whole_field INTEGER NOT NULL DEFAULT 0 CHECK (whole_field IN (0, 1));
