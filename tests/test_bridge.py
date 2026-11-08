"""Bridge: volts to mV, calibration and readings end to end against the API (track B)."""

import json

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from backend import db as backend_db  # noqa: E402
from backend.seed import seed  # noqa: E402
from bridge.boards import BOARDS, detect_sign, volts_to_mv  # noqa: E402
from bridge.bridge import Probe, calibrate, read_field  # noqa: E402

BOARD = BOARDS["ph4502c"]
NERNST_25C = 59.16


def volts_for_ph(ph, board=BOARD, sign=1):
    return board["mid_v"] + sign * (7 - ph) * NERNST_25C * board["gain"] / 1000


class FakeArduino:
    """Replies like the firmware. `script` is the list of pH values to report, in order."""

    def __init__(self, script, temp=25.0, sign=1):
        self.script, self.temp, self.sign, self.pending = list(script), temp, sign, b""

    def write(self, data):
        cmd = data.decode().strip()
        if cmd == "P":
            reply = {"ok": True, "fw": "1.0"}
        else:
            reply = {"ok": True, "ph_v": round(volts_for_ph(self.script.pop(0), sign=self.sign), 4),
                     "moist_raw": 480, "temp_c": self.temp, "n": 40}
        self.pending = (json.dumps(reply) + "\n").encode()

    def readline(self):
        line, self.pending = self.pending, b""
        return line


class ClientApi:
    def __init__(self, client):
        self.client = client
        token = client.post("/auth/login", json={"username": "operator", "password": "operator-pass"}).json()["token"]
        self.headers = {"Authorization": f"Bearer {token}"}

    def call(self, method, path, body=None):
        response = self.client.request(method, path, json=body, headers=self.headers)
        assert response.status_code < 300, response.text
        return response.json()


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("SEED_OPERATOR_PASSWORD", "operator-pass")
    conn = backend_db.connect(tmp_path / "bridge.db")
    seed(conn)
    backend_db.set_db(conn)
    from backend.main import app
    with TestClient(app) as client:
        yield ClientApi(client)
    backend_db.set_db(None)


@pytest.fixture(autouse=True)
def state_file(tmp_path, monkeypatch):
    import bridge.bridge
    monkeypatch.setattr(bridge.bridge, "STATE_FILE", tmp_path / "bridge_state.json")


def quiet(*_args):
    return ""


def test_volts_to_mv_round_trip():
    assert volts_to_mv(volts_for_ph(4.0), BOARD, 1) == pytest.approx(3 * NERNST_25C, abs=0.1)


@pytest.mark.parametrize("sign", [1, -1])
def test_sign_detected_from_buffers(sign):
    assert detect_sign(volts_for_ph(7, sign=sign), volts_for_ph(4, sign=sign)) == sign


def test_same_voltage_in_both_buffers_is_an_error():
    with pytest.raises(ValueError):
        detect_sign(2.5, 2.505)


@pytest.mark.parametrize("sign", [1, -1])
def test_calibrate_then_read_gives_correct_ph(api, sign):
    state = {}
    probe = Probe(FakeArduino([7, 7, 7, 4, 4, 4], sign=sign))
    cal = calibrate(probe, api, BOARD, "probe-1", ask=quiet, say=quiet, state=state)
    assert cal["accepted"] and cal["slope_pct"] == pytest.approx(100, abs=0.5)
    probe = Probe(FakeArduino([5.50, 5.52, 5.48], sign=sign))
    reading = read_field(probe, api, BOARD, "probe-1", 1, ask=quiet, say=quiet, state=state)
    assert reading["quality_status"] == "accepted" and reading["ph_water"] == pytest.approx(5.5, abs=0.02)


def test_wrong_board_gain_fails_calibration(api):
    wrong = dict(BOARD, gain=BOARD["gain"] * 1.2)      # 20% gain error -> slope about 83%
    probe = Probe(FakeArduino([7, 7, 7, 4, 4, 4]))
    cal = calibrate(probe, api, wrong, "probe-1", ask=quiet, say=quiet, state={})
    assert not cal["accepted"]


def test_drifting_buffer_reading_waits_until_steady(api):
    said = []
    probe = Probe(FakeArduino([7.0, 7.3, 7.0, 7, 7, 4, 4, 4]))
    cal = calibrate(probe, api, BOARD, "probe-1", ask=quiet, say=said.append, state={})
    assert cal["accepted"] and any("still settling" in s for s in said)


def test_two_step_calibration(api):
    from bridge.bridge import calibrate_ph4, calibrate_ph7
    state = {}
    calibrate_ph7(Probe(FakeArduino([7, 7, 7])), "probe-1", say=quiet, state=state)
    assert "probe-1" in state["pending"]
    cal = calibrate_ph4(Probe(FakeArduino([4, 4, 4])), api, BOARD, "probe-1", say=quiet, state=state)
    assert cal["accepted"] and cal["slope_pct"] == pytest.approx(100, abs=0.5)
    assert "probe-1" not in state["pending"] and state["probe-1"]["gain"] == BOARD["gain"]


def test_cal4_needs_cal7_first(api):
    from bridge.bridge import calibrate_ph4
    with pytest.raises(RuntimeError, match="cal7"):
        calibrate_ph4(Probe(FakeArduino([4] * 3)), api, BOARD, "probe-1", say=quiet, state={})


def test_read_needs_calibration_first(api):
    with pytest.raises(RuntimeError, match="calibrate"):
        read_field(Probe(FakeArduino([5.5] * 3)), api, BOARD, "probe-1", 1, ask=quiet, say=quiet, state={})


def test_watch_prints_voltage():
    from bridge.bridge import watch
    lines = []
    watch(Probe(FakeArduino([7.0, 7.0])), say=lines.append, count=2)
    assert len(lines) == 3 and "2.500 V" in lines[1]


def test_find_port_by_usb_chip():
    from types import SimpleNamespace as P
    from bridge.bridge import find_port
    ports = [P(device="COM3", vid=None, pid=None, description="Standard Serial over Bluetooth link"),
             P(device="COM11", vid=0x1A86, pid=0x7523, description="USB-SERIAL CH340 (COM11)")]
    assert find_port(ports) == "COM11"
    with pytest.raises(RuntimeError, match="no Arduino"):
        find_port(ports[:1])


class SilentPort:
    def write(self, data):
        pass

    def readline(self):
        return b""

    def close(self):
        pass


def test_probe_reconnects_when_the_board_stops_answering(monkeypatch):
    import bridge.bridge as bb
    monkeypatch.setattr(bb.time, "sleep", lambda s: None)
    opened = []
    def reopen():
        opened.append(1)
        return FakeArduino([7.0])
    probe = Probe(SilentPort(), reopen=reopen)
    assert probe.read()["ok"] and len(opened) == 1


def test_probe_gives_up_after_reconnects(monkeypatch):
    import bridge.bridge as bb
    monkeypatch.setattr(bb.time, "sleep", lambda s: None)
    probe = Probe(SilentPort(), reopen=SilentPort)
    with pytest.raises(RuntimeError, match="no reply"):
        probe.ping()


def test_read_uses_the_gain_saved_at_calibration(api):
    state = {}
    probe = Probe(FakeArduino([7, 7, 7, 4, 4, 4]))
    calibrate(probe, api, BOARD, "probe-1", ask=quiet, say=quiet, state=state)
    assert state["probe-1"]["gain"] == BOARD["gain"]
    other = dict(BOARD, gain=BOARD["gain"] * 1.5)        # e.g. a different preset later
    reading = read_field(Probe(FakeArduino([5.5] * 3)), api, other, "probe-1", 1, ask=quiet, say=quiet, state=state)
    assert reading["ph_water"] == pytest.approx(5.5, abs=0.02)


def test_sample_registers_field_and_fills_samples_csv(api, tmp_path):
    import csv
    from bridge.bridge import read_sample
    samples = tmp_path / "samples.csv"
    header = ["sample_id", "lat", "lon", "gps_accuracy_m", "probe_ph_1", "probe_ph_2", "probe_ph_3", "probe_temp_c", "notes"]
    with samples.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerow(["S01", "-15.679223", "28.217512", "3", "", "", "", "", "test"])
        writer.writerow(["S02", "-15.679295", "28.217410", "2.5", "", "", "", "", ""])
    state = {}
    calibrate(Probe(FakeArduino([7, 7, 7, 4, 4, 4])), api, BOARD, "probe-1", ask=quiet, say=quiet, state=state)
    result = read_sample(Probe(FakeArduino([5.9, 5.6, 5.52, 5.5, 5.51])), api, BOARD, "probe-1", "S01",
                         say=quiet, state=state, samples_csv=samples)
    assert result["quality_status"] == "accepted"
    rows = list(csv.DictReader(samples.open()))
    assert rows[0]["probe_ph_1"] and abs(float(rows[0]["probe_ph_2"]) - 5.5) < 0.05 and rows[1]["probe_ph_1"] == ""
    again = read_sample(Probe(FakeArduino([5.5] * 3)), api, BOARD, "probe-1", "S01", say=quiet, state=state, samples_csv=samples)
    assert again["field_id"] == result["field_id"]            # same field reused


def test_login_is_remembered(api):
    from bridge.bridge import ensure_login
    real = api
    class FakeApi:
        base = "http://test"
        token = None
        def login(self, username, password):
            self.token = real.headers["Authorization"].split()[1]
        def call(self, method, path, body=None):
            if self.token != real.headers["Authorization"].split()[1]:
                raise RuntimeError("server said 401")
            return {"username": "operator"}
    asked = []
    first = FakeApi()
    ensure_login(first, ask=lambda p: asked.append(p) or "operator", ask_secret=lambda p: "operator-pass", say=quiet)
    second = FakeApi()
    ensure_login(second, ask=lambda p: asked.append(p) or "operator", ask_secret=lambda p: "x", say=quiet)
    assert len(asked) == 1 and second.token == first.token


def test_live_mode_saves_each_sample_and_shows_it_on_the_dashboard(api):
    from bridge.bridge import live
    state = {}
    calibrate(Probe(FakeArduino([7, 7, 7, 4, 4, 4])), api, BOARD, "probe-1", ask=quiet, say=quiet, state=state)
    # sample 1 settles, probe stays, then moves to sample 2, which settles
    probe = Probe(FakeArduino([5.5, 5.5, 5.5, 5.5, 5.5, 6.5, 6.5, 6.5, 6.5, 6.5]))
    assert live(probe, api, BOARD, "probe-1", 1, say=quiet, state=state, rounds=2) == 2
    history = api.call("GET", "/fields/1/history")["readings"]
    assert [r["ph_water"] for r in history][:2] == pytest.approx([6.5, 5.5], abs=0.02)
    shown = api.call("GET", "/devices/probe-1/live")
    assert shown["settled"] and shown["ph"] == pytest.approx(6.5, abs=0.02)


def test_readings_do_not_send_moisture(api):
    state = {}
    calibrate(Probe(FakeArduino([7, 7, 7, 4, 4, 4])), api, BOARD, "probe-1", ask=quiet, say=quiet, state=state)
    reading = read_field(Probe(FakeArduino([5.5] * 3)), api, BOARD, "probe-1", 1, ask=quiet, say=quiet, state=state)
    assert reading.get("moisture") is None


def test_live_mode_follows_the_field_open_on_the_dashboard(api):
    from bridge.bridge import active_field, live
    state = {}
    calibrate(Probe(FakeArduino([7, 7, 7, 4, 4, 4])), api, BOARD, "probe-1", ask=quiet, say=quiet, state=state)
    with pytest.raises(RuntimeError):
        active_field(api, "probe-1", say=quiet, wait=0, tries=2)          # no Live page open yet
    api.call("POST", "/devices/probe-1/active-field", {"field_id": 1})
    assert live(Probe(FakeArduino([6.0] * 4)), api, BOARD, "probe-1", None, say=quiet, state=state, rounds=1) == 1
    assert api.call("GET", "/fields/1/history")["readings"][0]["ph_water"] == pytest.approx(6.0, abs=0.02)
