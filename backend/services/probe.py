"""Turn buffer millivolts into a calibration and probe millivolts into pH (S1-4b).

Works on electrode millivolts. Converting a particular sensor board's output
voltage to electrode millivolts is the bridge's job, because it depends on the
board (spec 2.3; boards not yet confirmed).
"""

from engine.quality import check_calibration

FARADAY_FACTOR = 0.198416   # mV per pH per kelvin (2.303 RT/F)


def theoretical_slope_mv(temp_c):
    return FARADAY_FACTOR * (temp_c + 273.15)


def calibrate(mv_ph7, mv_ph4, temp_c):
    """Return (offset_mv, slope_pct, reasons). Slope must be 95-105% (GLOSOLAN)."""
    slope_mv = (mv_ph4 - mv_ph7) / 3.0      # electrode mV rise from pH 7 to pH 4
    slope_pct = round(100 * slope_mv / theoretical_slope_mv(temp_c), 1)
    return mv_ph7, slope_pct, check_calibration(slope_pct)


def mv_to_ph(mv, offset_mv, slope_pct, temp_c):
    slope_mv = theoretical_slope_mv(temp_c) * slope_pct / 100
    return round(7.0 - (mv - offset_mv) / slope_mv, 2)
