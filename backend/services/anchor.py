"""Keep each probe's lab anchor up to date (see engine/anchor.py).

Every accepted reading of a probe carries the probe's current offset:
    ph_water = raw pH - lab_offset
so the raw value is always ph_water + lab_offset. When a new lab result arrives
for a sampling point the probe measured, the offset is learned again and applied
to the probe's readings, old and new. Advice already given is kept as it was.
"""

from engine.anchor import anchor_offset


def lab_pairs(db, device_id):
    """(raw probe pH, lab pH, lab method) for each lab result whose sampling point this
    probe also measured, newest lab result first."""
    rows = db.execute(
        "SELECT l.ph AS lab_ph, l.ph_method, r.ph_water, r.lab_offset FROM lab_results l "
        "JOIN readings r ON r.reading_id = (SELECT MAX(r2.reading_id) FROM readings r2 "
        "  WHERE r2.field_id = l.field_id AND UPPER(r2.point_label) = UPPER(l.point_label) "
        "  AND r2.device_id = ? AND r2.quality_status = 'accepted' AND r2.ph_water IS NOT NULL) "
        "WHERE l.point_label IS NOT NULL ORDER BY l.lab_id DESC", (device_id,)).fetchall()
    return [(r["ph_water"] + (r["lab_offset"] or 0), r["lab_ph"], r["ph_method"]) for r in rows]


def refresh_anchor(db, device_id):
    """Learn the probe's offset again and apply it to all its accepted readings."""
    anchor = anchor_offset(lab_pairs(db, device_id))
    offset = anchor.offset if anchor else None
    with db:
        db.execute("UPDATE devices SET lab_offset = ?, lab_offset_n = ?, lab_offset_spread = ?, "
                   "lab_offset_at = CASE WHEN ? IS NULL THEN NULL ELSE datetime('now') END WHERE device_id = ?",
                   (offset, anchor.n if anchor else None, anchor.spread if anchor else None, offset, device_id))
        db.execute("UPDATE readings SET ph_water = ROUND(ph_water + COALESCE(lab_offset, 0) - COALESCE(?, 0), 2), "
                   "lab_offset = ? WHERE device_id = ? AND quality_status = 'accepted' AND ph_water IS NOT NULL",
                   (offset, offset, device_id))
    return anchor


def refresh_for_field(db, field_id):
    for (device_id,) in db.execute("SELECT DISTINCT device_id FROM readings WHERE field_id = ? "
                                   "AND device_id IS NOT NULL", (field_id,)).fetchall():
        refresh_anchor(db, device_id)


def device_offset(db, device_id):
    if not device_id:
        return None
    row = db.execute("SELECT lab_offset FROM devices WHERE device_id = ?", (device_id,)).fetchone()
    return row["lab_offset"] if row else None
