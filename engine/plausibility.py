"""Is an unusual pH the soil, or the probe? (Nov 2026)

A self-testing farmer cannot tell whether a strange number is a strange soil
or a dried-out, badly calibrated probe. This check looks at what the system
knows about the reading and says which is more likely, and what to do:

- ``ok``          nothing unusual.
- ``check_probe`` most likely the probe: recalibrate, check it in the pH 7.00
                  buffer, measure again.
- ``confirm_lab`` the probe looks right (calibrated, and a repeat reading
                  agrees) but the soil is unusual: confirm with a lab test
                  before acting on it.

Readings outside the plausible range (engine.config PH_PLAUSIBLE_MIN/MAX) never
get this far: the quality check rejects them as a probe fault.
"""

from dataclasses import dataclass, field

from engine.config import DEFAULT_CONFIG


@dataclass
class Plausibility:
    status: str
    reasons: list = field(default_factory=list)     # i18n keys, e.g. "check.map_gap"
    refer_lab: bool = False
    confirmed_by_repeat: bool = False

    def as_dict(self):
        return {"status": self.status, "reasons": self.reasons, "refer_lab": self.refer_lab,
                "confirmed_by_repeat": self.confirmed_by_repeat}


def assess(ph, *, map_ph=None, calibration_age_hours=None, previous_ph=None, config=DEFAULT_CONFIG):
    """ph: the accepted reading; previous_ph: an earlier accepted reading of the same
    field within config.REPEAT_DAYS (None if there is none)."""
    reasons = []
    repeat = previous_ph is not None and abs(ph - previous_ph) <= config.REPEAT_AGREE
    probe_doubt = False
    unusual = False

    if calibration_age_hours is None or calibration_age_hours > config.CAL_MAX_AGE_HOURS:
        reasons.append("check.cal_old")
        probe_doubt = True

    extreme = ph < config.PH_EXTREME_LOW or ph > config.PH_EXTREME_HIGH
    if extreme:
        unusual = True
        reasons.append("check.extreme_high" if ph > config.PH_EXTREME_HIGH else "check.extreme_low")

    if map_ph is not None and abs(ph - map_ph) > config.MAP_GAP_CHECK:
        unusual = True
        reasons.append("check.map_gap")

    if repeat:
        reasons.append("check.repeat_agrees")

    if not unusual and not probe_doubt:
        return Plausibility("ok", reasons, False, repeat)
    if unusual and repeat and not probe_doubt:
        return Plausibility("confirm_lab", reasons, True, True)
    if not unusual:                       # only the calibration is old
        return Plausibility("check_probe", reasons, False, repeat)
    reasons.append("check.retest")
    return Plausibility("check_probe", reasons, extreme, repeat)
