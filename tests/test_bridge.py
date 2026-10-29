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


def test_drifting_buffer_reading_is_repeated(api):
    asked = []
    probe = Probe(FakeArduino([7.0, 7.3, 7.0, 7, 7, 7, 4, 4, 4]))
    calibrate(probe, api, BOARD, "probe-1", ask=asked.append, say=quiet, state={})
    assert any("drifting" in a for a in asked)


def test_read_needs_calibration_first(api):
    with pytest.raises(RuntimeError, match="calibrate"):
        read_field(Probe(FakeArduino([5.5] * 3)), api, BOARD, "probe-1", 1, ask=quiet, say=quiet, state={})


def test_watch_prints_voltage():
    from bridge.bridge import watch
    lines = []
    watch(Probe(FakeArduino([7.0, 7.0])), say=lines.append, count=2)
    assert len(lines) == 3 and "2.500 V" in lines[1]
