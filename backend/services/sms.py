"""SMS through Africa's Talking (FR13). Sandbox unless AT_API_KEY is set."""

from backend import config
from engine.i18n import text

MAX_LEN = 160


def format_summary(advice, lang):
    """Short SMS from a saved advice result."""
    if advice["refusals"]:
        body = text(f"ref.{advice['refusals'][0]}", lang, crop=advice["crop"])["text"]
    else:
        lime = (advice["plan_a"] or {}).get("lime") or {}
        per_lima = lime.get("per_lima")
        crops = ", ".join((advice["plan_c"] or {}).get("crops", [])[:3])
        parts = []
        if per_lima:
            parts.append(f"Lime {per_lima['low']:.0f}-{per_lima['high']:.0f} kg/lima")
        elif lime.get("status") == "not_needed":
            parts.append("No lime needed")
        if crops:
            parts.append(f"Suits now: {crops}")
        body = ". ".join(parts) or text("msg.MSG-08", lang)["text"]
    message = f"SoilSense: {advice['crop']}. {body}"
    return message if len(message) <= MAX_LEN else message[:MAX_LEN - 3].rsplit(" ", 1)[0] + "..."


def send_sms(phone, message):
    if not config.AT_API_KEY:
        return {"status": "stubbed"}
    try:
        import africastalking
    except ImportError:
        return {"status": "error: africastalking not installed"}
    try:
        africastalking.initialize(config.AT_USERNAME, config.AT_API_KEY)
        africastalking.SMS.send(message, [phone], config.AT_SENDER_ID or None)
        return {"status": "sent"}
    except Exception as error:     # report, never crash the request
        return {"status": f"error: {error}"}
