"""Measurement and engine settings (spec 0 rule 7, 2.3, 2.4, 2.6).

These are measurement limits and engineering defaults, not agronomy values.
Each can be overridden with an environment variable of the same name.
"""

import os
from dataclasses import dataclass, field


def _env_float(name, default):
    value = os.environ.get(name)
    return float(value) if value not in (None, "") else default


@dataclass(frozen=True)
class EngineConfig:
    # Largest probe error against the lab (RQ1). Provisional until validation.
    E_PROBE: float = field(default_factory=lambda: _env_float("E_PROBE", 0.5))
    # Calibration slope must be within this % of theoretical (GLOSOLAN).
    SLOPE_MIN_PCT: float = 95.0
    SLOPE_MAX_PCT: float = 105.0
    # Three replicates must lie within this spread (GLOSOLAN).
    REPLICATES: int = 3
    REPLICATE_SPREAD_MAX: float = 0.1
    # [PROPOSED] suspension temperature within calibration temperature +/- this.
    TEMP_TOLERANCE_C: float = field(default_factory=lambda: _env_float("TEMP_TOLERANCE_C", 5.0))
    # [PROPOSED] pH outside this range is a probe fault, not soil.
    PH_PLAUSIBLE_MIN: float = 3.5
    PH_PLAUSIBLE_MAX: float = 9.5
    # [PROPOSED] Plausibility check (Nov 2026): an accepted pH beyond these is
    # possible soil but rare; it is confirmed by a repeat reading or a lab test.
    # Above 8.5 soils are usually sodic; below 4.5 strongly acid.
    PH_EXTREME_LOW: float = 4.5
    PH_EXTREME_HIGH: float = 8.5
    # [PROPOSED] probe and map further apart than this: check the probe first.
    MAP_GAP_CHECK: float = field(default_factory=lambda: _env_float("MAP_GAP_CHECK", 1.5))
    # [PROPOSED] a calibration older than this does not count as "today's".
    CAL_MAX_AGE_HOURS: float = 24.0
    # [PROPOSED] two readings of the same field within this many days that agree
    # within REPEAT_AGREE confirm that the probe, not chance, gave the value.
    REPEAT_AGREE: float = 0.3
    REPEAT_DAYS: int = 30
    # GPS fixes worse than this are rejected (spec 2.2).
    GPS_MAX_ACCURACY_M: float = 30.0
    # [AGR C2, unsourced] water pH minus CaCl2 pH, as a range.
    PH_WATER_MINUS_CACL2: tuple = (0.5, 0.8)
    # [PROPOSED] flag advice as borderline when pH is this close to a band edge.
    BORDERLINE_MARGIN: float = field(default_factory=lambda: _env_float("BORDERLINE_MARGIN", 0.5))


DEFAULT_CONFIG = EngineConfig()
