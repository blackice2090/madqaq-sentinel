"""M6.1 web backend: camera-free WebSocket tests (fake tracker, synthetic JPEG frames, fake clock)."""
from __future__ import annotations

import json
import struct
from datetime import datetime, timedelta, timezone

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from apps.dual_channel_demo.main import handle_key
from apps.web_api import config
from apps.web_api.protocol import COMMANDS, ProtocolError, jpeg_dimensions, parse_command
from apps.web_api.session import SessionManager
from sentinel.dual_channel import DualChannelCoordinator
from sentinel.vision.config import MissingDependencyError
from sentinel.vision.tracker import TrackedPerson
from sentinel.vision.zones import ZoneSet
from simulator.scenarios import procedure as make_procedure

X = {"A": 0.13, "B": 0.38, "C": 0.63, "D": 0.87}
FRAMES_PER_ZONE = 15   # 1.5 s per zone at the fake 100 ms clock: well past dwell + smoothing


def jpeg(w: int = 160, h: int = 120) -> bytes:
    ok, buf = cv2.imencode(".jpg", np.full((h, w, 3), 90, np.uint8))
    assert ok
    return buf.tobytes()



class ScriptTracker:
    """Stands in for the M1 YOLO/ByteTrack tracker. `zone` = where the fake person stands (None = nobody)."""

    def __init__(self):
        self.zone: str | None = None
        self.resets = 0

    def update(self, frame):
        assert frame.ndim == 3          # a really decoded image reached the tracker
        if self.zone is None:
            return []
        x = X[self.zone]
        return [TrackedPerson(1, 0.9, (x - 0.03, 0.2, x + 0.03, 0.95))]

    def reset(self):
        self.resets += 1


class Clock:
    def __init__(self):
        self.t = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)

    def __call__(self):
        self.t += timedelta(milliseconds=100)
        return self.t


@pytest.fixture
def env():
    trackers: list[ScriptTracker] = []

    def factory(cfg):
        t = ScriptTracker()
        trackers.append(t)
        return t

    manager = SessionManager(ZoneSet.load("config/checkpoint_zones.json"), make_procedure(),
                             tracker_factory=factory, clock=Clock())
    previous = getattr(app.state, "web_sessions", None)
    app.state.web_sessions = manager
    client = TestClient(app)
    yield client, manager, trackers
    app.state.web_sessions = previous


class Conn:
    def __init__(self, ws, manager, trackers):
        self.ws = ws
        self.hello = ws.receive_json()
        self.state = ws.receive_json()
        self.session = manager.get(self.hello["session_id"])
        self._trackers = trackers

    def frame(self, data: bytes | None = None) -> dict:
        self.ws.send_bytes(data if data is not None else jpeg())
        msg = self.ws.receive_json()
        if msg["type"] == "error":
            self.last_error = msg
            msg = self.ws.receive_json()
        assert msg["type"] == "state"
        self.state = msg
        return msg

    def walk(self, steps: str) -> dict:
        self.frame()  # first frame creates this session's tracker
        tracker = self.session.pipeline.tracker
        for z in steps:
            tracker.zone = z
            for _ in range(FRAMES_PER_ZONE):
                self.frame()
        tracker.zone = None
        return self.frame()

    def command(self, name: str) -> tuple[dict, dict]:
        self.ws.send_text(json.dumps({"command": name}))
        ack = self.ws.receive_json()
        state = self.ws.receive_json()
        self.state = state
        return ack, state


# ---- 13. existing /health --------------------------------------------------------
def test_existing_health_unchanged(env):
    client, _, _ = env
    r = client.get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok", "engine_version": "m0.1"}


def test_web_health(env):
    client, _, _ = env
    body = client.get("/web/health").json()
    assert body["status"] == "ok" and body["digital_simulated"] is True and body["active_sessions"] == 0
    assert isinstance(body["websocket_support"], bool)


# ---- 2. session creation -----------------------------------------------------------
def test_session_creation(env):
    client, manager, trackers = env
    with client.websocket_connect("/ws/session") as ws:
        c = Conn(ws, manager, trackers)
        assert c.hello["type"] == "hello" and c.hello["protocol"] == config.PROTOCOL_VERSION
        assert c.hello["session_id"] == c.state["session_id"]
        assert [z["zone_id"] for z in c.hello["zones"]] == ["A", "B", "C", "D"]
        assert c.state["verdict"] == "WAITING" and c.state["journey_id"] is None
        assert manager.count == 1
        assert client.get("/web/health").json()["active_sessions"] == 1
        assert trackers == []            # no model before the user's first frame


# ---- full dual-channel scenarios through the socket ------------------------------
def test_full_physical_and_full_digital_completes(env):
    client, manager, trackers = env
    with client.websocket_connect("/ws/session") as ws:
        c = Conn(ws, manager, trackers)
        st = c.walk("ABCD")
        assert st["physical_trace"] == ["A", "B", "C", "D"] and st["journey_id"]
        ack, st = c.command("digital_full")
        assert ack["ok"] and st["verdict"] == "COMPLETED" and st["violation_types"] == []
        assert [s["state"] for s in st["step_states"]] == ["CONFIRMED"] * 4


def test_skip_b_with_full_digital_is_phantom(env):
    client, manager, trackers = env
    with client.websocket_connect("/ws/session") as ws:
        c = Conn(ws, manager, trackers)
        c.walk("ACD")
        _, st = c.command("digital_full")
        assert st["verdict"] == "VIOLATED" and "PHANTOM_COMPLETION" in st["violation_types"]
        assert "PHANTOM COMPLETION" in st["violation_labels"]


def test_physical_b_with_b_failed_is_contradiction(env):
    client, manager, trackers = env
    with client.websocket_connect("/ws/session") as ws:
        c = Conn(ws, manager, trackers)
        c.walk("ABCD")
        _, st = c.command("digital_b_failed")
        assert "CHANNEL_CONTRADICTION" in st["violation_types"]
        assert {"step_id": "B", "failed": True} in st["digital_trace"]


# ---- 3 / 4. isolation and reset -------------------------------------------------------
def test_session_isolation_and_targeted_reset(env):
    client, manager, trackers = env
    with client.websocket_connect("/ws/session") as w1, client.websocket_connect("/ws/session") as w2:
        a, b = Conn(w1, manager, trackers), Conn(w2, manager, trackers)
        a.walk("AB")
        b.walk("ABC")
        assert a.state["journey_id"] != b.state["journey_id"]
        assert a.state["physical_trace"] == ["A", "B"] and b.state["physical_trace"] == ["A", "B", "C"]
        assert a.session.pipeline.tracker is not b.session.pipeline.tracker
        assert a.session.coordinator is not b.session.coordinator
        b.command("digital_full")
        assert a.session.coordinator.digital_events() == []
        _, st = a.command("reset")
        assert st["journey_id"] is None and st["physical_trace"] == [] and st["verdict"] == "WAITING"
        assert b.session.coordinator.active_journey_id == b.state["journey_id"]
        assert b.frame()["physical_trace"] == ["A", "B", "C"]
        assert len(b.session.coordinator.digital_events()) == 4


# ---- 5. commands == M2 semantics ------------------------------------------------------
@pytest.mark.parametrize("steps", ["ABCD", "ACD", "AB"])
@pytest.mark.parametrize("command,key", [("digital_full", "1"), ("digital_without_b", "2"), ("digital_b_failed", "3")])
def test_digital_commands_match_m2_keyboard_semantics(env, walk, steps, command, key):
    client, manager, trackers = env
    physical = walk(steps)
    session = manager.create()
    try:
        session.coordinator.add_physical_events(physical)
        ok, _ = session.apply(parse_command(json.dumps({"command": command})))
        assert ok
        ref = DualChannelCoordinator(make_procedure())
        ref.add_physical_events(physical)

        class _P:
            def reset(self): pass
        handle_key(ord(key), ref, _P())
        got, want = session.coordinator.result(), ref.result()
        assert got.overall_status == want.overall_status
        assert [(v.type, v.step_id) for v in got.violations] == [(v.type, v.step_id) for v in want.violations]
        assert [(e.step_id, e.event_type) for e in session.coordinator.digital_events()] == \
            [(e.step_id, e.event_type) for e in ref.digital_events()]
        assert all(e.metadata == {"source": "m2_digital_simulator", "simulated": True}
                   for e in session.coordinator.digital_events())
        # clear == key "0"
        session.apply(parse_command('{"command": "digital_clear"}'))
        handle_key(ord("0"), ref, _P())
        assert session.coordinator.result().overall_status == ref.result().overall_status
        assert session.coordinator.digital_events() == []
    finally:
        manager.remove(session.session_id)


def test_double_injection_rejected_and_clear_allows_reinject(env):
    client, manager, trackers = env
    with client.websocket_connect("/ws/session") as ws:
        c = Conn(ws, manager, trackers)
        c.walk("ABCD")
        assert c.command("digital_full")[0]["ok"]
        ack, _ = c.command("digital_b_failed")
        assert not ack["ok"] and "CLEAR DIGITAL" in ack["message"]
        assert c.command("digital_clear")[0]["ok"]
        assert c.command("digital_b_failed")[0]["ok"]


def test_digital_without_journey_is_rejected(env):
    client, manager, trackers = env
    with client.websocket_connect("/ws/session") as ws:
        c = Conn(ws, manager, trackers)
        ack, st = c.command("digital_full")
        assert ack["ok"] is False and st["journey_id"] is None


# ---- 6. invalid commands ------------------------------------------------------------
@pytest.mark.parametrize("text,code", [
    ("not json", "invalid_json"),
    ("[]", "invalid_command"),
    ('{"command": "rm -rf"}', "invalid_command"),
    ('{"command": "reset", "path": "/etc/passwd"}', "invalid_command"),
    ('{"command": 1}', "invalid_command"),
    ('{"cmd": "reset"}', "invalid_command"),
    ('{"command": "' + "x" * 5000 + '"}', "message_too_large"),
])
def test_invalid_commands_rejected(env, text, code):
    client, manager, trackers = env
    with client.websocket_connect("/ws/session") as ws:
        Conn(ws, manager, trackers)
        ws.send_text(text)
        msg = ws.receive_json()
        assert msg == {"type": "error", "code": code, "message": msg["message"]}
        assert "/" not in msg["message"] or "etc" not in msg["message"]
        ws.send_text('{"command": "ping"}')
        assert ws.receive_json()["type"] == "pong"   # connection still healthy


def test_command_table_is_closed():
    assert set(COMMANDS) == {"reset", "digital_full", "digital_without_b", "digital_b_failed",
                             "digital_clear", "ping", "get_evidence"}
    with pytest.raises(ProtocolError):
        parse_command('{"command": "__import__"}')


# ---- 7 / 8. image validation and size limits ----------------------------------------
@pytest.mark.parametrize("payload", [b"", b"\x00" * 100, b"\xff\xd8\xff\xe0\x00\x10JFIF", b"\xff\xd8" + b"\xab" * 64,
                                     jpeg()[:40]])
def test_invalid_image_bytes_do_not_crash(env, payload):
    client, manager, trackers = env
    with client.websocket_connect("/ws/session") as ws:
        c = Conn(ws, manager, trackers)
        st = c.frame(payload)
        assert c.last_error["code"] == "invalid_image"
        assert st["type"] == "state"
        assert c.frame()["frame"]["width"] == 160    # a valid frame afterwards still works


def _fake_sof(w: int, h: int) -> bytes:
    sof = b"\xff\xc0" + struct.pack(">HBHHB", 11, 8, h, w, 1) + b"\x01\x11\x00"
    return b"\xff\xd8" + sof + b"\xff\xd9"


def test_jpeg_dimensions_reads_header():
    assert jpeg_dimensions(jpeg(200, 100)) == (200, 100)
    assert jpeg_dimensions(_fake_sof(3000, 50)) == (3000, 50)


def test_frame_byte_limit_enforced(env):
    client, manager, trackers = env
    with client.websocket_connect("/ws/session") as ws:
        c = Conn(ws, manager, trackers)
        c.frame(b"\xff\xd8" + b"\x00" * (config.MAX_FRAME_BYTES + 10))
        assert c.last_error["code"] == "frame_too_large"
        assert trackers == []        # rejected before any analysis


def test_frame_pixel_limit_enforced_before_decoding(env):
    client, manager, trackers = env
    with client.websocket_connect("/ws/session") as ws:
        c = Conn(ws, manager, trackers)
        c.frame(_fake_sof(config.MAX_FRAME_WIDTH + 1, 100))
        assert c.last_error["code"] == "frame_too_large"


# ---- 9. schema -------------------------------------------------------------------------
STATE_KEYS = {
    "type", "protocol", "session_id", "journey_id", "frame", "vision", "detections", "zones", "active_zone",
    "expected", "physical_trace", "digital_trace", "step_states", "verdict", "engine_status", "violation_types",
    "violation_labels", "finding", "finding_where", "extra_findings", "timeline", "digital_active",
    "digital_simulated", "notice", "disclosures",
}


def test_state_schema_is_stable(env):
    client, manager, trackers = env
    with client.websocket_connect("/ws/session") as ws:
        c = Conn(ws, manager, trackers)
        assert set(c.state) == STATE_KEYS
        c.walk("AB")
        st = c.state
        assert set(st) == STATE_KEYS
        assert set(st["frame"]) == {"width", "height", "seq"}
        assert st["vision"]["status"] == "ready"
        c.session.pipeline.tracker.zone = "B"
        st = c.frame()
        det = st["detections"][0]
        assert set(det) == {"tracker_id", "confidence", "box", "zone_id", "in_active_journey"}
        assert all(0.0 <= v <= 1.0 for v in det["box"]) and st["active_zone"] == "B"
        assert {"step_id", "name", "state", "indicator", "word"} == set(st["step_states"][0])
        assert set(st["timeline"][0]) == {"event_id", "timestamp", "channel", "step_id", "step_name",
                                          "event_type", "confidence", "simulated"}
        assert len(st["timeline"]) <= config.TIMELINE_LIMIT
        assert all(set(z) == {"zone_id", "name", "x1", "y1", "x2", "y2"} for z in st["zones"])


# ---- 10 / 11. simulated disclosure and privacy ---------------------------------------------
def test_digital_simulated_and_disclosures(env):
    client, manager, trackers = env
    with client.websocket_connect("/ws/session") as ws:
        c = Conn(ws, manager, trackers)
        assert c.hello["digital_simulated"] is True and c.state["digital_simulated"] is True
        d = c.state["disclosures"]
        assert d["digital_label"] == "SIMULATED DIGITAL CHANNEL"
        assert d["digital_note"] == "Local simulator — not a production checkpoint integration."
        assert d["privacy"] == "Temporary tracking only • No face recognition • No persistent identity"
        assert "Sampled camera frames are sent to the local MADQAQ analysis backend" in d["frames"]
        c.walk("ABCD")
        _, st = c.command("digital_full")
        assert st["digital_simulated"] is True and st["digital_active"] is True
        assert all(t["simulated"] for t in st["timeline"] if t["channel"] == "DIGITAL")
        assert all(t["confidence"] is not None for t in st["timeline"] if t["channel"] == "PHYSICAL")


def test_no_forbidden_claims_in_web_payloads(env):
    client, manager, trackers = env
    with client.websocket_connect("/ws/session") as ws:
        c = Conn(ws, manager, trackers)
        blob = json.dumps([c.hello, c.state, client.get("/web/health").json()]).lower()
    for phrase in ("95% camera accuracy", "98.1% accuracy", "production ready", "real checkpoint integration"):
        assert phrase not in blob


# ---- evidence ------------------------------------------------------------------------------
def test_evidence_export(env):
    client, manager, trackers = env
    with client.websocket_connect("/ws/session") as ws:
        c = Conn(ws, manager, trackers)
        ws.send_text('{"command": "get_evidence"}')
        assert ws.receive_json()["code"] == "no_journey"
        c.walk("ACD")
        c.command("digital_full")
        ws.send_text('{"command": "get_evidence"}')
        msg = ws.receive_json()
        assert msg["type"] == "evidence"
        ev = msg["evidence"]
        assert ev["journey_id"] == c.state["journey_id"]
        assert ev["verdict"] == "VIOLATED" and "PHANTOM_COMPLETION" in ev["violation_types"]
        assert ev["digital_simulated"] is True and ev["disclosures"]["digital_label"] == "SIMULATED DIGITAL CHANNEL"
        assert ev["physical_trace"] == ["A", "C", "D"] and ev["digital_trace"] == ["A", "B", "C", "D"]
        assert len(ev["timeline"]) == len(ev["physical_events"]) + len(ev["digital_events"])
        assert all(datetime.fromisoformat(t["timestamp"]).tzinfo for t in ev["timeline"])
        assert ev["export"]["frames_saved"] is False and ev["image_file"] is None
        text = json.dumps(ev).lower()
        for k in ("face", "embedding", "biometric", "tracker_id"):
            assert f'"{k}' not in text
        json.loads(json.dumps(ev))   # valid JSON


# ---- 12. cleanup ------------------------------------------------------------------------------
def test_session_cleanup_on_disconnect(env):
    client, manager, trackers = env
    with client.websocket_connect("/ws/session") as ws:
        c = Conn(ws, manager, trackers)
        c.walk("AB")
        session = c.session
        assert manager.count == 1
    assert manager.count == 0 and manager.get(session.session_id) is None
    assert session.closed and session.coordinator.active_journey_id is None
    assert session.emitter.journeys == {} and session.pipeline.tracker is None


# ---- robustness ---------------------------------------------------------------------------------
def test_foreign_origin_rejected(env):
    client, manager, trackers = env
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/session", headers={"origin": "https://evil.example"}) as ws:
            ws.receive_json()
    assert manager.count == 0


def test_local_origin_accepted(env):
    client, manager, trackers = env
    with client.websocket_connect("/ws/session", headers={"origin": "http://localhost:3000"}) as ws:
        assert ws.receive_json()["type"] == "hello"


def test_session_limit(env):
    client, manager, trackers = env
    manager.max_sessions = 1
    with client.websocket_connect("/ws/session") as w1:
        Conn(w1, manager, trackers)
        with client.websocket_connect("/ws/session") as w2:
            assert w2.receive_json()["code"] == "session_limit"
    assert manager.count == 0


def test_vision_unavailable_is_reported_safely(env):
    client, manager, trackers = env

    def broken(cfg):
        raise MissingDependencyError('Vision dependencies are not installed. Run:  pip install -e ".[vision]"')
    manager.tracker_factory = broken
    with client.websocket_connect("/ws/session") as ws:
        c = Conn(ws, manager, trackers)
        st = c.frame()
        assert c.last_error["code"] == "vision_unavailable"
        assert st["vision"]["status"] == "unavailable"
        ws.send_text('{"command": "reset"}')
        assert ws.receive_json()["ok"] is True


def test_cors_is_localhost_only(env):
    client, _, _ = env
    ok = client.get("/web/health", headers={"origin": "http://localhost:3000"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:3000"
    bad = client.get("/web/health", headers={"origin": "https://evil.example"})
    assert "access-control-allow-origin" not in bad.headers


def test_allowed_origins_never_wildcard(monkeypatch):
    monkeypatch.setenv("MADQAQ_WEB_ORIGINS", "*, http://localhost:4000/")
    assert config.allowed_origins() == ("http://localhost:4000",)
