"""Reading quality check (spec 2.3, FR4, NFR2).

A reading that fails here gets trust level None and no advice.
"""

from dataclasses import dataclass, field
from typing import Optional

from .config import DEFAULT_CONFIG

# Readings are rounded to the probe's display precision before comparing,
# so that 0.10 passes and 0.11 fails regardless of float noise.
_PRECISION = 3


@dataclass
class Calibration:
    """Result of the two-buffer calibration (pH 7.00 offset, pH 4.00 slope)."""
    slope_pct: float
    temp_c: float


@dataclass
class QualityResult:
    accepted: bool
    ph_mean: Optional[float]
    reasons: list = field(default_factory=list)    # why it was rejected
    warnings: list = field(default_factory=list)   # recorded, not rejecting


def check_calibration(slope_pct, config=DEFAULT_CONFIG):
    """Return a list of reasons the calibration is invalid (empty if valid)."""
    slope = round(slope_pct, _PRECISION)
    if not config.SLOPE_MIN_PCT <= slope <= config.SLOPE_MAX_PCT:
        return [f"calibration slope {slope_pct:.1f}% outside "
                f"{config.SLOPE_MIN_PCT:.0f}-{config.SLOPE_MAX_PCT:.0f}%"]
    return []


def check_reading(replicates, temp_c, calibration, moisture=None, config=DEFAULT_CONFIG):
    """Accept or reject one probe reading.

    replicates  : pH values from the same suspension (three expected)
    temp_c      : suspension temperature from the DS18B20
    calibration : Calibration in force, or None
    moisture    : raw moisture value (thresholds are OPEN, so never rejects)
    """
    reasons, warnings = [], []

    if calibration is None:
        reasons.append("no valid calibration")
    else:
        reasons += check_calibration(calibration.slope_pct, config)

    values = [float(v) for v in replicates if v is not None]
    if len(values) != config.REPLICATES:
        reasons.append(f"expected {config.REPLICATES} replicates, got {len(values)}")
    elif round(max(values) - min(values), _PRECISION) > config.REPLICATE_SPREAD_MAX:
        reasons.append(f"replicates spread {max(values) - min(values):.2f} "
                       f"exceeds {config.REPLICATE_SPREAD_MAX}")

    ph_mean = round(sum(values) / len(values), 2) if values else None
    if ph_mean is not None and not (config.PH_PLAUSIBLE_MIN <= ph_mean <= config.PH_PLAUSIBLE_MAX):
        reasons.append(f"pH {ph_mean} outside plausible range "
                       f"{config.PH_PLAUSIBLE_MIN}-{config.PH_PLAUSIBLE_MAX} (probe fault)")

    if temp_c is None:
        reasons.append("no suspension temperature")
    elif calibration is not None and abs(temp_c - calibration.temp_c) > config.TEMP_TOLERANCE_C:
        reasons.append(f"temperature {temp_c:.1f} C outside calibration "
                       f"{calibration.temp_c:.1f} +/- {config.TEMP_TOLERANCE_C:.0f} C")

    if moisture is not None:
        warnings.append("moisture recorded but not checked: thresholds OPEN (spec 2.3)")

    accepted = not reasons
    return QualityResult(accepted, ph_mean if accepted else None, reasons, warnings)
