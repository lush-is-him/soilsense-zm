"""Spec 2.4, 2.5, 10: trust checker."""

from engine.config import EngineConfig
from engine.map_service import MapEstimate
from engine.quality import QualityResult
from engine.trust import HIGH, LOW, MODERATE, NONE, assess

PASSED = QualityResult(True, 5.6)
FAILED = QualityResult(False, None, ["replicates spread 0.30 exceeds 0.1"])
MAP = MapEstimate(ph_mean=6.0, ph_sd=0.2, oc_g_kg=7.0, p_ppm=7.0, k_ppm=160.0, texture="Loam")


def test_agree_gives_moderate_and_map_chemistry():
    result = assess(PASSED, "gps", 10, MAP)       # |5.6 - 6.0| = 0.4 <= 0.5 + 0.2
    assert result.level == MODERATE and result.use_map_chemistry
    assert result.threshold == 0.7 and result.difference == 0.4


def test_agreement_boundary_is_inclusive():
    exact = QualityResult(True, 5.3)              # |5.3 - 6.0| = 0.7 == T
    assert assess(exact, "gps", 10, MAP).level == MODERATE
    assert assess(QualityResult(True, 5.29), "gps", 10, MAP).level == LOW


def test_disagree_gives_low_without_map_chemistry():
    result = assess(QualityResult(True, 4.8), "gps", 10, MAP)
    assert result.level == LOW and not result.use_map_chemistry


def test_no_map_value_gives_low():
    assert assess(PASSED, "gps", 10, None).level == LOW


def test_manual_location_gives_low():
    assert assess(PASSED, "manual", None, MAP).level == LOW


def test_gps_worse_than_30m_gives_low():
    assert assess(PASSED, "gps", 30, MAP).level == MODERATE
    assert assess(PASSED, "gps", 45, MAP).level == LOW


def test_lab_result_gives_high_even_if_reading_failed():
    assert assess(FAILED, "gps", 10, MAP, lab_result={"ph": 5.2}).level == HIGH


def test_failed_reading_gives_none():
    assert assess(FAILED, "gps", 10, MAP).level == NONE


def test_e_probe_change_moves_threshold():
    strict = EngineConfig(E_PROBE=0.1)
    assert assess(PASSED, "gps", 10, MAP, config=strict).level == LOW
