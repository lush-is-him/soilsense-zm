# ============================================================
# SoilSense ZM — Backend
# sms.py — Africa's Talking SMS integration
#
# Sends SMS advisories to farmers after soil health prediction.
# Currently stubbed — set AT_API_KEY and AT_USERNAME to activate.
# ============================================================

import os

# ── CONFIG ────────────────────────────────────────────────────
# Set these environment variables or replace with your credentials
AT_USERNAME = os.environ.get("AT_USERNAME", "sandbox")
AT_API_KEY = os.environ.get("AT_API_KEY", "")
AT_SENDER_ID = os.environ.get("AT_SENDER_ID", "SoilSense")

# Whether SMS is enabled (False until API key is configured)
SMS_ENABLED = bool(AT_API_KEY)


def send_sms(phone: str, message: str) -> dict:
    """
    Send an SMS via Africa's Talking.

    Args:
        phone: Recipient phone number (e.g. +260971234567)
        message: SMS message body (max 160 chars for single SMS)

    Returns:
        dict with status and details
    """
    if not SMS_ENABLED:
        print(f"   📱 SMS STUB: Would send to {phone}")
        print(f"   Message: {message[:100]}...")
        return {
            "status": "stubbed",
            "phone": phone,
            "message": message,
            "note": "Set AT_API_KEY environment variable to enable real SMS"
        }

    try:
        import africastalking

        africastalking.initialize(AT_USERNAME, AT_API_KEY)
        sms = africastalking.SMS

        response = sms.send(
            message=message,
            recipients=[phone],
            sender_id=AT_SENDER_ID if AT_USERNAME != "sandbox" else None
        )

        print(f"   ✅ SMS sent to {phone}")
        return {
            "status": "sent",
            "phone": phone,
            "response": response
        }

    except ImportError:
        print("   ⚠️ africastalking package not installed. Run: pip install africastalking")
        return {"status": "error", "message": "africastalking package not installed"}

    except Exception as e:
        print(f"   ❌ SMS failed: {e}")
        return {"status": "error", "message": str(e)}


def format_advisory_sms(soil_health: str, confidence: float, advisory_summary: str) -> str:
    """
    Format a concise SMS message from prediction results.
    Keeps under 160 characters for single SMS pricing.
    """
    alert_emoji = {
        "Healthy": "🟢",
        "Moderate": "🟡",
        "Degraded": "🟠",
        "Critical": "🔴"
    }

    emoji = alert_emoji.get(soil_health, "ℹ️")

    # Truncate summary to fit in SMS
    max_summary_len = 90
    short_summary = advisory_summary[:max_summary_len]
    if len(advisory_summary) > max_summary_len:
        short_summary = short_summary.rsplit(' ', 1)[0] + "..."

    msg = f"{emoji} SoilSense ZM: Soil={soil_health} ({confidence:.0f}%). {short_summary}"

    return msg[:160]
