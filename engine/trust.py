"""Map agreement rule and trust levels (spec 2.4, 2.5)."""

from dataclasses import dataclass, field
from typing import Optional

from .config import DEFAULT_CONFIG

HIGH, MODERATE, LOW, NONE = "high", "moderate", "low", "none"


@dataclass
class TrustResult:
    level: str
    reasons: list = field(default_factory=list)
    threshold: Optional[float] = None    # T = e_probe + s_map
    difference: Optional[float] = None   # |pH_probe - pH_map|
    use_map_chemistry: bool = False      # OC, P, K, texture from the map


def assess(quality, location_source, gps_accuracy_m, map_estimate,
           lab_result=None, config=DEFAULT_CONFIG):
    """Assign the trust level for one reading.

    quality         : QualityResult from engine.quality
    location_source : "gps" or "manual"
    gps_accuracy_m  : reported accuracy of the GPS fix (None for manual)
    map_estimate    : MapEstimate or None
    lab_result      : any non-None lab result means High (lab takes precedence)
    """
    if lab_result is not None:
        return TrustResult(HIGH, ["lab results entered"])
    if quality is None or not quality.accepted:
        return TrustResult(NONE, ["reading failed quality check"])

    if location_source != "gps":
        return TrustResult(LOW, ["location entered manually"])
    if gps_accuracy_m is None or gps_accuracy_m > config.GPS_MAX_ACCURACY_M:
        return TrustResult(LOW, [f"GPS accuracy worse than {config.GPS_MAX_ACCURACY_M:.0f} m"])
    if map_estimate is None:
        return TrustResult(LOW, ["no map value at this location"])

    threshold = round(config.E_PROBE + map_estimate.ph_sd, 3)
    difference = round(abs(quality.ph_mean - map_estimate.ph_mean), 3)
    if difference <= threshold:
        return TrustResult(MODERATE, ["probe and map agree"], threshold, difference, True)
    return TrustResult(LOW, ["probe and map disagree"], threshold, difference)
