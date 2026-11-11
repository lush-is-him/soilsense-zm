"""Who may see and change which farmers and fields (self-testing model, Nov 2026).

- farmer : only their own profile and fields.
- officer: farmers who agreed to share their results, farmers the officer
           registered, and any farmer who asked for a lab test or a visit.
           May test, enter lab results and handle referrals for those farmers;
           may edit the profiles of farmers they registered.
- admin  : everything.

Every route that touches a farmer, field, reading or recommendation goes
through these checks; a record the user may not see answers 404, so its
existence is not revealed.
"""

from fastapi import HTTPException

FARMER, OFFICER, ADMIN = "farmer", "officer", "admin"


def own_farmer_id(db, user):
    row = db.execute("SELECT farmer_id FROM farmers WHERE user_id = ?", (user["user_id"],)).fetchone()
    return row["farmer_id"] if row else None


def visible_farmers_sql(user):
    """(WHERE clause on table alias f, params) limiting farmers to what the user may see."""
    if user["role"] == ADMIN:
        return "1 = 1", ()
    if user["role"] == FARMER:
        return "f.user_id = ?", (user["user_id"],)
    return ("(f.share_consent = 1 OR f.created_by = ? OR EXISTS (SELECT 1 FROM referrals r "
            "JOIN fields fl ON fl.field_id = r.field_id WHERE fl.farmer_id = f.farmer_id))",
            (user["user_id"],))


def can_see_farmer(db, user, farmer_id):
    where, params = visible_farmers_sql(user)
    return db.execute(f"SELECT 1 FROM farmers f WHERE f.farmer_id = ? AND {where}",
                      (farmer_id, *params)).fetchone() is not None


def farmer_for(db, user, farmer_id, edit_profile=False):
    """The farmer row if the user may see it (and edit its profile); else 404 or 403."""
    row = db.execute("SELECT * FROM farmers WHERE farmer_id = ?", (farmer_id,)).fetchone()
    if row is None or not can_see_farmer(db, user, farmer_id):
        raise HTTPException(404, f"Farmer {farmer_id} not found")
    farmer = dict(row, sms_consent=bool(row["sms_consent"]), share_consent=bool(row["share_consent"]))
    if edit_profile and user["role"] != ADMIN:
        mine = farmer["user_id"] == user["user_id"]
        registered = user["role"] == OFFICER and farmer["created_by"] == user["user_id"] \
            and farmer["user_id"] is None
        if not (mine or registered):
            raise HTTPException(403, "Only the farmer, the officer who registered them, or an admin "
                                     "can change this profile")
    return farmer


def field_for(db, user, field_id):
    """The field row if the user may see its farmer; else 404."""
    row = db.execute("SELECT * FROM fields WHERE field_id = ?", (field_id,)).fetchone()
    if row is None or not can_see_farmer(db, user, row["farmer_id"]):
        raise HTTPException(404, f"Field {field_id} not found")
    return dict(row)


def require_field_edit(db, user, field):
    """Renaming, moving or deleting a field: its farmer, the registering officer, or admin."""
    farmer_for(db, user, field["farmer_id"], edit_profile=True)
