"""POST /advice and friends (FR7, FR10, FR12, FR13)."""

import json
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException

from backend.access import field_for, visible_farmers_sql
from backend.auth import current_user
from backend.db import get_db
from backend.routes.farmers import farmer_or_404
from backend.routes.fields import field_or_404, get_or_fetch_map_estimate
from backend.schemas import AdviceIn
from backend.services.rules_sync import sync_rules
from backend.services.sms import format_summary, send_sms
from engine.advice import AdviceRequest, Advisor
from engine.i18n import text
from engine.config import DEFAULT_CONFIG
from engine.map_service import MapEstimate
from engine.plausibility import assess as plausibility
from engine.quality import QualityResult
from engine.trust import HIGH, MODERATE, assess

router = APIRouter(tags=["Advice"])


def _latest(db, sql, field_id):
    row = db.execute(sql, (field_id,)).fetchone()
    return dict(row) if row else None


def _texture(lab, check, estimate, trust_level):
    """Lab first, then the latest texture-by-feel, then the map when trusted."""
    if lab and lab.get("texture"):
        return lab["texture"], "lab"
    if check and check.get("texture_by_feel"):
        return check["texture_by_feel"], "field_check"
    if estimate and estimate.get("texture") and trust_level == MODERATE:
        return estimate["texture"], "map"
    return None, None


def render(result, lang):
    """Re-render the user-facing text of a saved result in another language."""
    result = dict(result)
    result["messages"] = [text(m["key"], lang) for m in result["messages"]]
    result["refusal_text"] = [text(f"ref.{r}", lang, crop=result["crop"]) for r in result["refusals"]]
    if result.get("trust_text"):
        result["trust_text"] = text(result["trust_text"]["key"], lang)
    result["lang"] = lang
    return result


def _hours_since(sql_ts):
    if not sql_ts:
        return None
    then = datetime.fromisoformat(sql_ts.replace(" ", "T")).replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - then).total_seconds() / 3600


def _plausibility(db, reading, estimate):
    """Probe problem or unusual soil? Only for an accepted probe reading."""
    calibration = db.execute("SELECT date FROM calibrations WHERE calibration_id = ?",
                             (reading["calibration_id"],)).fetchone() if reading["calibration_id"] else None
    since = (datetime.now(timezone.utc) - timedelta(days=DEFAULT_CONFIG.REPEAT_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
    previous = db.execute(
        "SELECT ph_water FROM readings WHERE field_id = ? AND reading_id < ? AND quality_status = 'accepted' "
        "AND ts >= ? ORDER BY reading_id DESC LIMIT 1",
        (reading["field_id"], reading["reading_id"], since)).fetchone()
    return plausibility(reading["ph_water"], map_ph=estimate["ph_mean"] if estimate else None,
                        calibration_age_hours=_hours_since(calibration["date"]) if calibration else None,
                        previous_ph=previous["ph_water"] if previous else None).as_dict()


@router.post("/advice", status_code=201)
def create_advice(body: AdviceIn, db=Depends(get_db), user=Depends(current_user)):
    field = field_for(db, user, body.field_id)
    reading = None
    if body.reading_id is not None:
        reading = db.execute("SELECT * FROM readings WHERE reading_id = ? AND field_id = ?",
                             (body.reading_id, body.field_id)).fetchone()
        if reading is None:
            raise HTTPException(404, f"Reading {body.reading_id} not found for this field")
    lab = _latest(db, "SELECT * FROM lab_results WHERE field_id = ? ORDER BY lab_id DESC LIMIT 1",
                  body.field_id)
    if reading is None and lab is None:
        raise HTTPException(422, "Need a reading_id or a lab result for this field")

    quality = (QualityResult(reading["quality_status"] == "accepted", reading["ph_water"])
               if reading else None)
    estimate = get_or_fetch_map_estimate(db, field)
    map_estimate = MapEstimate(estimate["ph_mean"], estimate["ph_sd"], estimate["oc"], estimate["p"],
                               estimate["k"], estimate["texture"]) if estimate else None
    trust = assess(quality, field["location_source"], field["gps_accuracy_m"], map_estimate, lab)

    if trust.level == HIGH:
        ph, method = lab["ph"], lab["ph_method"]
    else:
        ph, method = (quality.ph_mean if quality else None), "water"
    check = _latest(db, "SELECT * FROM field_checks WHERE field_id = ? ORDER BY check_id DESC LIMIT 1",
                    body.field_id)
    texture, texture_source = _texture(lab, check, estimate, trust.level)

    ruleset = sync_rules(db)
    as_of = body.as_of_date or date.today()
    result = Advisor(ruleset).advise(AdviceRequest(
        ph=ph if ph is not None else 0.0, ph_method=method, trust_level=trust.level,
        crop=body.crop, as_of_date=as_of, water=body.water, budget_band=body.budget_band,
        texture=texture, texture_source=texture_source, lang=body.lang))
    result["trust"] = {"level": trust.level, "reasons": trust.reasons,
                       "threshold": trust.threshold, "difference": trust.difference}
    result["texture"] = {"value": texture, "source": texture_source}
    result["map_estimate"] = estimate if trust.use_map_chemistry else None
    result["map_ph"] = estimate["ph_mean"] if estimate else None
    result["checks"] = (_plausibility(db, reading, estimate)
                        if reading is not None and trust.level != HIGH and reading["quality_status"] == "accepted"
                        else {"status": "ok", "reasons": [], "refer_lab": False, "confirmed_by_repeat": False})
    result["field_id"] = body.field_id
    result["reading_id"] = body.reading_id

    with db:
        cur = db.execute(
            "INSERT INTO recommendations (reading_id, field_id, trust_level, crop, budget_band, water, "
            "plan_a, plan_b, plan_c, result, language, as_of_date, method_sensitive, user_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (body.reading_id, body.field_id, trust.level, body.crop, body.budget_band, body.water,
             json.dumps(result["plan_a"]), json.dumps(result["plan_b"]), json.dumps(result["plan_c"]),
             json.dumps(result), body.lang, as_of.isoformat(), int(result["method_sensitive"]), user["user_id"]))
        rec_id = cur.lastrowid
        for rule in result["fired_rules"]:
            db.execute("INSERT INTO recommendation_rules (rec_id, rule_id, rule_version) "
                       "SELECT ?, rule_id, version FROM rules WHERE rule_id = ?", (rec_id, rule["id"]))
    result["rec_id"] = rec_id
    return result


def _saved(db, rec_id, user):
    row = db.execute("SELECT * FROM recommendations WHERE rec_id = ?", (rec_id,)).fetchone()
    if row is None:
        raise HTTPException(404, f"Advice {rec_id} not found")
    field_for(db, user, row["field_id"])
    return row


@router.get("/advice")
def recent_advice(limit: int = 5, db=Depends(get_db), user=Depends(current_user)):
    """The latest recommendations the user may see, newest first (home page)."""
    where, params = visible_farmers_sql(user)
    rows = db.execute(
        "SELECT r.rec_id, r.crop, r.trust_level, r.as_of_date, fl.field_id, fl.name AS field, f.alias AS farmer "
        "FROM recommendations r JOIN fields fl ON fl.field_id = r.field_id "
        f"JOIN farmers f ON f.farmer_id = fl.farmer_id WHERE {where} ORDER BY r.rec_id DESC LIMIT ?",
        (*params, max(1, min(limit, 50))))
    return [dict(r) for r in rows]


@router.get("/advice/{rec_id}")
def get_advice(rec_id: int, lang: str = "en", db=Depends(get_db), user=Depends(current_user)):
    row = _saved(db, rec_id, user)
    result = render(json.loads(row["result"]), lang)
    result["rec_id"] = rec_id
    result["rule_versions"] = {r["rule_id"]: r["rule_version"] for r in db.execute(
        "SELECT rule_id, rule_version FROM recommendation_rules WHERE rec_id = ?", (rec_id,))}
    return result


@router.post("/advice/{rec_id}/sms")
def send_advice_sms(rec_id: int, db=Depends(get_db), user=Depends(current_user)):
    row = _saved(db, rec_id, user)
    field = field_or_404(db, row["field_id"])
    farmer = farmer_or_404(db, field["farmer_id"])
    if not (farmer["sms_consent"] and farmer["phone"]):
        raise HTTPException(409, "Farmer has not consented to SMS or has no phone number")
    message = format_summary(json.loads(row["result"]), farmer["preferred_language"])
    outcome = send_sms(farmer["phone"], message)
    with db:
        db.execute("INSERT INTO sms_messages (rec_id, status) VALUES (?, ?)", (rec_id, outcome["status"]))
    return {"status": outcome["status"], "message": message}
