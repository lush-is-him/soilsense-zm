"""Lab anchor: correct a probe with the constant error it shows against the laboratory.

The ZARI results (Nov 2026) showed the probe reading higher than the laboratory by
nearly the same amount at every sample (1.31 pH, SD 0.20, against CaCl2), while
ranking the samples correctly (r = 0.89). Part of the gap is the method (water
against CaCl2), part is the probe and the field method. A single offset, learned
from samples measured with the probe and also sent to the lab, removes most of
it: leave-one-out MAE 0.25 instead of 1.31 (scripts/analyse_lab.py).

The offset is in the water scale used by the rules, so it is
    probe pH - lab pH in water
with a CaCl2 lab result converted by the midpoint of PH_WATER_MINUS_CACL2.
"""

import statistics
from typing import NamedTuple, Optional

from engine.config import DEFAULT_CONFIG


class Anchor(NamedTuple):
    offset: float          # subtract from the probe's pH
    n: int                 # lab pairs used
    spread: Optional[float]  # SD of the pair differences (None for one pair)


def lab_in_water(ph, method, config=DEFAULT_CONFIG):
    if method == "cacl2":
        low, high = config.PH_WATER_MINUS_CACL2
        return ph + (low + high) / 2
    return ph


def anchor_offset(pairs, config=DEFAULT_CONFIG):
    """pairs: (probe pH as measured, lab pH, lab method), newest first."""
    diffs = [probe - lab_in_water(lab, method, config) for probe, lab, method in pairs][:config.LAB_ANCHOR_MAX_PAIRS]
    if len(diffs) < config.LAB_ANCHOR_MIN_PAIRS:
        return None
    spread = round(statistics.stdev(diffs), 2) if len(diffs) > 1 else None
    return Anchor(round(statistics.mean(diffs), 2), len(diffs), spread)
