"""Laptop serial bridge: probe over USB to the SoilSense API (spec 2, track B).

    python -m bridge.bridge ports
    python -m bridge.bridge test      --port COM3
    python -m bridge.bridge watch     --port COM3     (live pH volts; Ctrl+C to stop)
    python -m bridge.bridge calibrate --port COM3 --board ph4502c --device probe-1
    python -m bridge.bridge read      --port COM3 --board ph4502c --device probe-1 --field 1
    python -m bridge.bridge moisture  --port COM3

The server address defaults to http://localhost:8000 (--api to change).
You are asked for your SoilSense username and password.
"""

import argparse
import getpass
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from bridge.boards import BOARDS, detect_sign, volts_to_mv

STATE_FILE = Path.home() / ".soilsense_bridge.json"
STABLE_V = 0.005          # three buffer readings must agree within 5 mV of board output
REPLICATES = 3


# ----- serial ----------------------------------------------------------

class Probe:
    """Talks to the Arduino. `port` is any object with write() and readline()."""

    def __init__(self, port):
        self.port = port

    def command(self, letter, attempts=3):
        line = ""
        for attempt in range(attempts):
            self.port.write(f"{letter}\n".encode())
            line = self.port.readline().decode(errors="replace").strip()
            if line.startswith("{"):
                break
            time.sleep(1)                     # board still starting up, or a stray partial line
        if not line.startswith("{"):
            raise RuntimeError("no reply from the probe: unplug the USB cable, wait 5 seconds, "
                               "plug it back in and try again (see 'Port problems' in firmware/README.md)")
        reply = json.loads(line)
        if not reply.get("ok"):
            raise RuntimeError(f"probe error: {reply.get('error')}")
        return reply

    def ping(self):
        return self.command("P")

    def read(self):
        return self.command("R")


def open_serial(name):
    import serial      # pyserial

    port = serial.Serial(name, 9600, timeout=5)
    time.sleep(2.5)    # the Uno resets when the port opens
    port.reset_input_buffer()
    return port


# ----- API -------------------------------------------------------------

class Api:
    def __init__(self, base, token=None):
        self.base = base.rstrip("/")
        self.token = token

    def call(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(self.base + path, data=data, method=method)
        request.add_header("Content-Type", "application/json")
        if self.token:
            request.add_header("Authorization", f"Bearer {self.token}")
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read() or b"null")
        except urllib.error.HTTPError as error:
            detail = error.read().decode(errors="replace")
            raise RuntimeError(f"server said {error.code}: {detail}") from None
        except urllib.error.URLError as error:
            raise RuntimeError(f"cannot reach {self.base}: {error.reason}") from None

    def login(self, username, password):
        self.token = self.call("POST", "/auth/login", {"username": username, "password": password})["token"]


# ----- local state (sign of the board per device) ---------------------

def load_state():
    try:
        return json.loads(STATE_FILE.read_text())
    except (OSError, ValueError):
        return {}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))


# ----- steps -----------------------------------------------------------

def stable_volts(probe, ask, label):
    """Read until three consecutive readings agree; return their mean volts and temperature."""
    while True:
        readings = [probe.read() for _ in range(3)]
        volts = [r["ph_v"] for r in readings]
        if max(volts) - min(volts) <= STABLE_V:
            return statistics.mean(volts), statistics.mean(r["temp_c"] for r in readings)
        ask(f"  {label}: still drifting ({min(volts):.3f}-{max(volts):.3f} V). "
            "Wait 30 seconds, then press Enter to try again.")


def calibrate(probe, api, board, device_id, ask=input, say=print, state=None):
    state = load_state() if state is None else state
    ask("Rinse the probe with distilled water, put it in the pH 7.00 buffer, wait 1 minute, press Enter.")
    v7, t7 = stable_volts(probe, ask, "pH 7.00")
    say(f"  pH 7.00 buffer: {v7:.4f} V at {t7:.1f} C")
    ask("Rinse the probe, put it in the pH 4.00 buffer, wait 1 minute, press Enter.")
    v4, t4 = stable_volts(probe, ask, "pH 4.00")
    say(f"  pH 4.00 buffer: {v4:.4f} V at {t4:.1f} C")

    sign = detect_sign(v7, v4)
    result = api.call("POST", f"/devices/{device_id}/calibrations", {
        "mv_ph7": volts_to_mv(v7, board, sign), "mv_ph4": volts_to_mv(v4, board, sign),
        "temp_c": round((t7 + t4) / 2, 1)})
    state[device_id] = {"sign": sign}
    save_state(state)
    if result["accepted"]:
        say(f"Calibration ACCEPTED: slope {result['slope_pct']}%.")
    else:
        say(f"Calibration REJECTED: {'; '.join(result['reasons'])}. "
            "Check the buffers are fresh, the probe is clean, and the board gain is right.")
    return result


def read_field(probe, api, board, device_id, field_id, ask=input, say=print, state=None):
    state = load_state() if state is None else state
    if device_id not in state:
        raise RuntimeError(f"calibrate {device_id} first (python -m bridge.bridge calibrate ...)")
    sign = state[device_id]["sign"]
    ask("Mix the sieved soil with water (1:2.5), stir, wait 1 minute, put the probe in. Press Enter.")
    replicates, temps, moistures = [], [], []
    for i in range(1, REPLICATES + 1):
        if i > 1:
            ask(f"Stir again, wait 30 seconds, press Enter for reading {i} of {REPLICATES}.")
        reply = probe.read()
        replicates.append(volts_to_mv(reply["ph_v"], board, sign))
        temps.append(reply["temp_c"])
        moistures.append(reply["moist_raw"])
        say(f"  reading {i}: {reply['ph_v']:.4f} V, {reply['temp_c']:.1f} C")
    result = api.call("POST", "/readings", {
        "field_id": field_id, "device_id": device_id, "replicates_mv": replicates,
        "temp_c": round(statistics.mean(temps), 1), "moisture": round(statistics.mean(moistures))})
    if result["quality_status"] == "accepted":
        say(f"Reading ACCEPTED: pH {result['ph_water']} (reading #{result['reading_id']}).")
    else:
        say(f"Reading REJECTED: {'; '.join(result['quality_reasons'])}.")
    return result


def watch(probe, say=print, count=None):
    """Print the pH board voltage about once a second, e.g. while setting the zero screw."""
    say("Showing the pH board voltage. Press Ctrl+C to stop.")
    shown = 0
    try:
        while count is None or shown < count:
            reply = probe.read()
            say(f"  pH board: {reply['ph_v']:.3f} V    temperature: {reply['temp_c']:.1f} C")
            shown += 1
    except KeyboardInterrupt:
        say("Stopped.")


def moisture_points(probe, ask=input, say=print):
    """Two-point moisture calibration (spec 2.3, thresholds OPEN): print raw values."""
    ask("Hold the moisture sensor in open air (dry), press Enter.")
    dry = probe.read()["moist_raw"]
    ask("Put the sensor in a glass of water up to the line, press Enter.")
    wet = probe.read()["moist_raw"]
    say(f"Dry (air): {dry}   Wet (water): {wet}")
    say("Send these two numbers to the developer: they set the waterlogging threshold.")
    return dry, wet


# ----- command line ------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=["ports", "test", "watch", "calibrate", "read", "moisture"])
    parser.add_argument("--port", help="serial port, e.g. COM3 (Windows) or /dev/ttyACM0")
    parser.add_argument("--board", choices=sorted(BOARDS), default="ph4502c")
    parser.add_argument("--gain", type=float, help="override the board gain")
    parser.add_argument("--device", default="probe-1")
    parser.add_argument("--field", type=int, help="field id (for read)")
    parser.add_argument("--api", default="http://localhost:8000")
    args = parser.parse_args(argv)

    if args.action == "ports":
        from serial.tools import list_ports
        for port in list_ports.comports():
            print(f"{port.device}  {port.description}")
        return 0
    if not args.port:
        parser.error("--port is required")

    board = dict(BOARDS[args.board])
    if args.gain:
        board["gain"] = args.gain
    if not board["confirmed"]:
        print(f"Note: the '{args.board}' gain ({board['gain']}) is a typical value, not confirmed "
              f"for your board. See bridge/boards.py.")
    try:
        probe = Probe(open_serial(args.port))
    except Exception as error:     # pyserial raises SerialException or OSError
        print(f"ERROR: cannot open {args.port}: {error}")
        print("  - Close the Arduino IDE (and its Serial Monitor); only one program can use the port.")
        print("  - Unplug the USB cable, wait 5 seconds, plug it back in, and try again.")
        print("  - 'A device attached to the system is not functioning' usually means the CH340")
        print("    USB chip stopped responding: see 'Port problems' in firmware/README.md.")
        return 1
    try:
        if args.action == "test":
            print("Firmware:", probe.ping())
            print("Reading:", probe.read())
            return 0
        if args.action == "watch":
            watch(probe)
            return 0
        if args.action == "moisture":
            moisture_points(probe)
            return 0
        api = Api(args.api)
        api.login(input("SoilSense username: "), getpass.getpass("Password: "))
        if args.action == "calibrate":
            calibrate(probe, api, board, args.device)
        else:
            if args.field is None:
                parser.error("--field is required for read")
            read_field(probe, api, board, args.device, args.field)
        return 0
    except RuntimeError as error:
        print(f"ERROR: {error}")
        return 1
    except OSError as error:          # pyserial's SerialException, e.g. "Write timeout"
        print(f"ERROR: the Arduino stopped responding on {args.port} ({error}).")
        print("  Unplug the USB cable, wait 5 seconds, plug it back in and try again.")
        print("  If this keeps happening, see 'Port problems' in firmware/README.md.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
