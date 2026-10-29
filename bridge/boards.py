"""pH sensor board presets: how board output volts relate to electrode millivolts.

    electrode_mV = sign * (volts - mid_v) * 1000 / gain

`gain` is the board's amplification. The values below are typical figures
for common boards, NOT confirmed for your hardware: check the board's
datasheet or seller page and correct them. An error in `gain` shows up as a
wrong calibration slope %, so a correct gain is what makes the 95-105%
check meaningful. `sign` is detected during calibration (pH 4 must read a
higher electrode mV than pH 7), so it does not need to be known. `mid_v` only
shifts the offset, which the pH 7.00 calibration absorbs.
"""

BOARDS = {
    # PH-4502C (the board in use, confirmed from photo 29 Oct 2026; the gain is
    # still a typical value until the first calibration). BNC socket, two
    # potentiometers, pins To Do Po G G V+. Typically
    # about 0.18 V per pH around 2.5 V at pH 7, i.e. gain about 3.
    "ph4502c": {"gain": 3.0, "mid_v": 2.5, "confirmed": False},
    # DFRobot Gravity SEN0161 (v1). Seller formula pH = 3.5 * V + offset,
    # i.e. about 0.286 V per pH, gain about 4.8.
    "dfrobot_sen0161": {"gain": 4.83, "mid_v": 2.0, "confirmed": False},
    # Unknown board: set the gain yourself with --gain.
    "custom": {"gain": None, "mid_v": 2.5, "confirmed": False},
}


def volts_to_mv(volts, board, sign):
    if board["gain"] is None:
        raise ValueError("board gain unknown: pass --gain or choose a preset")
    return round(sign * (volts - board["mid_v"]) * 1000.0 / board["gain"], 2)


def detect_sign(volts_ph7, volts_ph4):
    """Electrode mV is higher at pH 4 than at pH 7; pick the sign that makes it so."""
    if abs(volts_ph4 - volts_ph7) < 0.01:
        raise ValueError("pH 4 and pH 7 buffers read almost the same voltage: "
                         "check the probe is connected and in the right buffer")
    return 1 if volts_ph4 > volts_ph7 else -1
