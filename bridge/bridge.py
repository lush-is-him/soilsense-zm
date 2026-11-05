"""Laptop serial bridge: probe over USB to the SoilSense API (spec 2, track B).

    python -m bridge.bridge ports
    python -m bridge.bridge test
    python -m bridge.bridge watch                     (live pH volts; Ctrl+C to stop)
    python -m bridge.bridge cal7      --device probe-1            (probe in pH 7.00)
    python -m bridge.bridge cal4      --board ph4502c --device probe-1   (probe in pH 4.00)
    python -m bridge.bridge calibrate --board ph4502c --device probe-1   (both in one run)
    python -m bridge.bridge read      --board ph4502c --device probe-1 --field 1
    python -m bridge.bridge sample S01 --board ph4502c --device probe-1  (retained lab sample)
    python -m bridge.bridge moisture

The Arduino is found automatically; add --port COM3 only if you have two.

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
STABLE_V = 0.01           # three buffer readings must agree within 10 mV of board output
REPLICATES = 3


# ----- serial ----------------------------------------------------------

class Probe:
    """Talks to the Arduino. `port` is any object with write() and readline()."""

    def __init__(self, port, reopen=None, reconnects=2):
        self.port = port
        self.reopen = reopen            # callable that opens the port again (like a replug)
        self.reconnects = reconnects

    def _exchange(self, letter, attempts):
        for attempt in range(attempts):
            self.port.write(f"{letter}\n".encode())
            line = self.port.readline().decode(errors="replace").strip()
            if line.startswith("{"):
                return line
            time.sleep(1)                     # board still starting up, or a stray partial line
        return ""

    def fresh(self):
        """Reconnect before measuring after a pause: clone USB chips go quiet when idle."""
        if self.reopen:
            self._reconnect()

    def _reconnect(self):
        try:
            self.port.close()
        except Exception:
            pass
        time.sleep(5)                   # give the USB chip time before reopening
        self.port = self.reopen()

    def command(self, letter, attempts=3):
        line = ""
        for round_ in range(1 + (self.reconnects if self.reopen else 0)):
            try:
                if round_:
                    print("  (no answer from the Arduino: reconnecting...)")
                    self._reconnect()
                line = self._exchange(letter, attempts)
            except OSError:                   # write timeout or device lost: try a reconnect
                line = ""
                if not self.reopen or round_ == self.reconnects:
                    raise
            if line:
                break
        if not line:
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


# USB IDs of the Arduino's USB chip: CH340 clones, genuine Uno (16U2), FTDI, CP210x.
KNOWN_USB_IDS = {(0x1A86, 0x7523), (0x1A86, 0x5523), (0x2341, 0x0043), (0x2341, 0x0001),
                 (0x2A03, 0x0043), (0x0403, 0x6001), (0x10C4, 0xEA60)}


def find_port(ports=None):
    """The Arduino's serial port, found by its USB chip, so the COM number never matters."""
    if ports is None:
        from serial.tools import list_ports
        ports = list_ports.comports()
    matches = [p.device for p in ports
               if (getattr(p, "vid", None), getattr(p, "pid", None)) in KNOWN_USB_IDS
               or "CH340" in (getattr(p, "description", "") or "")
               or "Arduino" in (getattr(p, "description", "") or "")]
    if not matches:
        raise RuntimeError("no Arduino found: check the USB cable is plugged in and the ON light is lit, "
                           "then unplug and replug it")
    if len(matches) > 1:
        raise RuntimeError(f"more than one Arduino found ({', '.join(matches)}): pass --port to choose")
    return matches[0]


def open_serial(name):
    import serial      # pyserial

    port = serial.Serial(name, 9600, timeout=5, write_timeout=5)
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


def ensure_login(api, ask=input, ask_secret=getpass.getpass, say=print):
    """Reuse the saved login (valid about 12 hours); ask for the password only when it has expired."""
    state = load_state()
    saved = state.get("login", {}).get(api.base)
    if saved:
        api.token = saved
        try:
            user = api.call("GET", "/auth/me")
            say(f"Logged in as {user['username']} (saved login).")
            return
        except RuntimeError:
            api.token = None
    api.login(ask("SoilSense username: "), ask_secret("Password: "))
    state = load_state()
    state.setdefault("login", {})[api.base] = api.token
    save_state(state)


# ----- local state (sign of the board per device) ---------------------

def load_state():
    try:
        return json.loads(STATE_FILE.read_text())
    except (OSError, ValueError):
        return {}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))


# ----- steps -----------------------------------------------------------

def stable_volts(probe, label, say=print, max_readings=180):
    """Read continuously until the last three readings agree; return their mean volts and temperature.

    Reading without pauses keeps the clone board's USB chip awake (it tends to drop
    off after quiet periods or quick reconnects).
    """
    say(f"  Measuring {label}: reading until steady (Ctrl+C to stop)...")
    readings = []
    for _ in range(max_readings):
        readings.append(probe.read())
        last = readings[-3:]
        volts = [r["ph_v"] for r in last]
        spread = max(volts) - min(volts)
        say(f"    {volts[-1]:.3f} V" + ("" if len(last) < 3 or spread <= STABLE_V else "   (still settling)"))
        if len(last) == 3 and spread <= STABLE_V:
            return statistics.mean(volts), statistics.mean(r["temp_c"] for r in last)
    raise RuntimeError(f"{label}: the reading did not settle. Rinse the probe, check it is in the buffer, try again")


def _post_calibration(api, board, device_id, v7, t7, v4, t4, state, say):
    sign = detect_sign(v7, v4)
    result = api.call("POST", f"/devices/{device_id}/calibrations", {
        "mv_ph7": volts_to_mv(v7, board, sign), "mv_ph4": volts_to_mv(v4, board, sign),
        "temp_c": round((t7 + t4) / 2, 1)})
    state[device_id] = {"sign": sign, "gain": board["gain"]}
    save_state(state)
    if result["accepted"]:
        say(f"Calibration ACCEPTED: slope {result['slope_pct']}%.")
    else:
        say(f"Calibration REJECTED: {'; '.join(result['reasons'])}. "
            "Check the buffers are fresh, the probe is clean, and the board gain is right.")
    return result


def calibrate(probe, api, board, device_id, ask=input, say=print, state=None):
    """Both buffers in one run."""
    state = load_state() if state is None else state
    ask("Rinse the probe with distilled water, put it in the pH 7.00 buffer, wait 1 minute, press Enter.")
    v7, t7 = stable_volts(probe, "pH 7.00", say)
    say(f"  pH 7.00 buffer: {v7:.4f} V at {t7:.1f} C")
    ask("Rinse the probe, put it in the pH 4.00 buffer, wait 1 minute, press Enter.")
    v4, t4 = stable_volts(probe, "pH 4.00", say)
    say(f"  pH 4.00 buffer: {v4:.4f} V at {t4:.1f} C")
    return _post_calibration(api, board, device_id, v7, t7, v4, t4, state, say)


def calibrate_ph7(probe, device_id, say=print, state=None):
    """Step 1 of 2: the probe is already in pH 7.00; measure and remember it."""
    state = load_state() if state is None else state
    v7, t7 = stable_volts(probe, "pH 7.00", say)
    state.setdefault("pending", {})[device_id] = {"v7": v7, "t7": t7}
    save_state(state)
    say(f"pH 7.00 saved: {v7:.4f} V at {t7:.1f} C.")
    say("Now rinse the probe, put it in pH 4.00, wait 2-3 minutes, then run the cal4 command.")
    return v7, t7


def calibrate_ph4(probe, api, board, device_id, say=print, state=None):
    """Step 2 of 2: the probe is already in pH 4.00; measure and finish the calibration."""
    state = load_state() if state is None else state
    pending = state.get("pending", {}).get(device_id)
    if not pending:
        raise RuntimeError("run cal7 first (with the probe in pH 7.00)")
    v4, t4 = stable_volts(probe, "pH 4.00", say)
    say(f"  pH 4.00 buffer: {v4:.4f} V at {t4:.1f} C")
    result = _post_calibration(api, board, device_id, pending["v7"], pending["t7"], v4, t4, state, say)
    state.get("pending", {}).pop(device_id, None)
    save_state(state)
    return result


def read_field(probe, api, board, device_id, field_id, ask=input, say=print, state=None):
    state = load_state() if state is None else state
    if device_id not in state:
        raise RuntimeError(f"calibrate {device_id} first (python -m bridge.bridge calibrate ...)")
    sign = state[device_id]["sign"]
    saved_gain = state[device_id].get("gain")
    if saved_gain and saved_gain != board["gain"]:
        say(f"  Using gain {saved_gain} from the last calibration (not {board['gain']}).")
        board = dict(board, gain=saved_gain)
    # The soil-water mix is prepared and the probe is in it before this runs.
    # Read continuously until steady (no pauses: the clone USB chip drops off
    # when idle) and use the three steady readings as the replicates.
    say("  Reading the sample until steady...")
    window = []
    for _ in range(180):
        window = (window + [probe.read()])[-REPLICATES:]
        volts = [r["ph_v"] for r in window]
        settled = len(window) == REPLICATES and max(volts) - min(volts) <= STABLE_V
        say(f"    {volts[-1]:.3f} V" + ("" if settled or len(window) < REPLICATES else "   (still settling)"))
        if settled:
            break
    else:
        raise RuntimeError("the reading did not settle: stir the sample, wait 2 minutes and try again")
    replicates = [volts_to_mv(r["ph_v"], board, sign) for r in window]
    temps = [r["temp_c"] for r in window]
    moistures = [r["moist_raw"] for r in window]
    result = api.call("POST", "/readings", {
        "field_id": field_id, "device_id": device_id, "replicates_mv": replicates,
        "temp_c": round(statistics.mean(temps), 1), "moisture": round(statistics.mean(moistures))})
    if result["quality_status"] == "accepted":
        say(f"Reading ACCEPTED: pH {result['ph_water']} (reading #{result['reading_id']}).")
    else:
        say(f"Reading REJECTED: {'; '.join(result['quality_reasons'])}.")
    return result


SAMPLES_CSV = Path(__file__).resolve().parent.parent / "docs" / "evaluation" / "samples.csv"
SAMPLE_FARMER = "Retained lab samples"


def sample_field(api, sample_id, samples_csv=SAMPLES_CSV):
    """The field for a retained lab sample (S01...), registered from samples.csv on first use."""
    import csv
    with open(samples_csv, newline="", encoding="utf-8") as handle:
        row = next((r for r in csv.DictReader(handle) if r["sample_id"] == sample_id), None)
    if row is None:
        raise RuntimeError(f"{sample_id} is not in {samples_csv.name}")
    if not (row.get("lat") and row.get("lon")):
        raise RuntimeError(f"{sample_id} has no GPS position in {samples_csv.name}")
    farmer = next((f for f in api.call("GET", "/farmers") if f["alias"] == SAMPLE_FARMER), None)
    if farmer is None:
        farmer = api.call("POST", "/farmers", {"alias": SAMPLE_FARMER})
    fields = api.call("GET", f"/farmers/{farmer['farmer_id']}")["fields"]
    field = next((f for f in fields if f["name"] == sample_id), None)
    if field is None:
        accuracy = float(row["gps_accuracy_m"]) if row.get("gps_accuracy_m") else None
        field = api.call("POST", "/fields", {
            "farmer_id": farmer["farmer_id"], "name": sample_id, "lat": float(row["lat"]),
            "lon": float(row["lon"]), "gps_accuracy_m": accuracy,
            "location_source": "gps" if accuracy is not None and accuracy <= 30 else "manual"})
    return field["field_id"]


def record_sample(sample_id, reading, samples_csv=SAMPLES_CSV):
    """Write the probe replicates and temperature into samples.csv for the evaluation."""
    import csv
    with open(samples_csv, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    fields = list(rows[0].keys())
    for row in rows:
        if row["sample_id"] == sample_id:
            for i, value in enumerate(reading["replicates"], start=1):
                row[f"probe_ph_{i}"] = f"{value:.2f}"
            row["probe_temp_c"] = f"{reading['temp_c']:.1f}"
    with open(samples_csv, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def read_sample(probe, api, board, device_id, sample_id, say=print, state=None, samples_csv=SAMPLES_CSV):
    field_id = sample_field(api, sample_id, samples_csv)
    result = read_field(probe, api, board, device_id, field_id, say=say, state=state)
    if result["quality_status"] == "accepted":
        record_sample(sample_id, result, samples_csv)
        say(f"Saved to {samples_csv.name}: {sample_id} pH " + ", ".join(f"{v:.2f}" for v in result["replicates"]))
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
    parser.add_argument("action", choices=["ports", "test", "watch", "cal7", "cal4", "calibrate", "read", "sample", "moisture"])
    parser.add_argument("sample_id", nargs="?", help="for sample: the sample code, e.g. S01")
    parser.add_argument("--port", help="serial port, e.g. COM3; found automatically if left out")
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
        try:
            args.port = find_port()
        except RuntimeError as error:
            print(f"ERROR: {error}")
            return 1
        print(f"Using the Arduino on {args.port}.")

    board = dict(BOARDS[args.board])
    if args.gain:
        board["gain"] = args.gain
    if not board["confirmed"] and not args.gain:
        print(f"Note: the '{args.board}' gain ({board['gain']}) is a typical value, not confirmed "
              f"for your board. See bridge/boards.py.")
    api = None
    if args.action in ("calibrate", "cal4", "read", "sample"):
        if args.action == "read" and args.field is None:
            parser.error("--field is required for read")
        if args.action == "sample" and not args.sample_id:
            parser.error("give the sample code, e.g. python -m bridge.bridge sample S01")
        # Log in before opening the port: the USB chip goes quiet while you type.
        api = Api(args.api)
        try:
            ensure_login(api)
        except RuntimeError as error:
            print(f"ERROR: {error}")
            return 1
    try:
        port_name = args.port
        probe = Probe(open_serial(port_name), reopen=lambda: open_serial(port_name))
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
        if args.action == "cal7":
            calibrate_ph7(probe, args.device)
            return 0
        if args.action == "cal4":
            calibrate_ph4(probe, api, board, args.device)
            return 0
        if args.action == "moisture":
            moisture_points(probe)
            return 0
        if args.action == "sample":
            read_sample(probe, api, board, args.device, args.sample_id.upper())
        elif args.action == "calibrate":
            calibrate(probe, api, board, args.device)
        else:
            read_field(probe, api, board, args.device, args.field)
        return 0
    except (RuntimeError, ValueError) as error:
        print(f"ERROR: {error}")
        return 1
    except OSError as error:          # pyserial's SerialException, e.g. "Write timeout"
        print(f"ERROR: the Arduino stopped responding on {args.port} ({error}).")
        print("  Unplug the USB cable, wait 5 seconds, plug it back in and try again.")
        print("  If this keeps happening, see 'Port problems' in firmware/README.md.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
