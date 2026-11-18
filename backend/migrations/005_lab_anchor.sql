-- Lab anchor (Nov 2026): a lab result can name the sampling point it came from, so it can
-- be paired with the probe's reading of the same sample; each probe keeps the offset learned
-- from those pairs, and each reading records the offset applied (raw pH = ph_water + lab_offset).
ALTER TABLE lab_results ADD COLUMN point_label TEXT;
ALTER TABLE devices ADD COLUMN lab_offset REAL;
ALTER TABLE devices ADD COLUMN lab_offset_n INTEGER;
ALTER TABLE devices ADD COLUMN lab_offset_spread REAL;
ALTER TABLE devices ADD COLUMN lab_offset_at TEXT;
ALTER TABLE readings ADD COLUMN lab_offset REAL;
