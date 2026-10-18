"""Per-browser MADQAQ session: its own M1 tracker/emitter/pipeline and its own M2 coordinator.

Nothing here re-implements zone, event or conformance logic: frames go through the existing
M1 PerceptionPipeline, physical events through the existing M2 DualChannelCoordinator, and
the state/evidence wording comes from the existing M3 presentation layer.
"""
from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from apps.web_api import config
from apps.web_api.protocol import COMMANDS, Command, ProtocolError, validate_frame
from sentinel.conformance.engine import ConformanceEngine
from sentinel.digital.presets import PRESETS
from sentinel.domain.models import ProcedureDefinition
from sentinel.dual_channel import DualChannelCoordinator, DualChannelError
from sentinel.dual_channel.state import DuplicateInjectionError, NoActiveJourneyError
from sentinel.presentation import build_dashboard_model, build_evidence, build_timeline
from sentinel.presentation import labels
from sentinel.vision.config import MissingDependencyError, VisionConfig, VisionError
from sentinel.vision.event_emitter import PhysicalEventEmitter
from sentinel.vision.pipeline import PerceptionPipeline, PersonView
from sentinel.vision.tracker import PersonTracker
from sentinel.vision.zones import ZoneSet

log = logging.getLogger("madqaq.web")

TrackerFactory = Callable[[VisionConfig], PersonTracker]
Clock = Callable[[], datetime]

RESET_TEXT = "Reset: physical journey, digital evidence and verdict cleared."   # same wording as M2
CLEAR_TEXT = "Simulated digital evidence cleared for the current journey."
DUPLICATE_TEXT = "Digital evidence is already present for this journey. Use CLEAR DIGITAL first, or RESET JOURNEY."


def default_tracker_factory(cfg: VisionConfig) -> PersonTracker:
    """The existing M1 YOLO + ByteTrack tracker. A NEW instance per session, so tracking state is isolated."""
    from sentinel.vision.tracker import UltralyticsByteTrackTracker
    return UltralyticsByteTrackTracker.load(cfg.model, cfg.confidence)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def decode_jpeg(data: bytes) -> Any:
    """Validated JPEG bytes -> BGR numpy image (in memory only; never written to disk)."""
    validate_frame(data)
    try:
        import cv2
        import numpy as np
    except ImportError:
        raise ProtocolError("vision_unavailable",
                            'OpenCV is not installed on the backend. Run: pip install -e ".[vision]"') from None
    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None or image.ndim != 3 or image.shape[0] == 0 or image.shape[1] == 0:
        raise ProtocolError("invalid_image", "The frame could not be decoded as a JPEG image.")
    return image


class WebSession:
    def __init__(self, session_id: str, zones: ZoneSet, procedure: ProcedureDefinition,
                 vision_config: VisionConfig, tracker_factory: TrackerFactory, clock: Clock = _utc_now):
        self.session_id = session_id
        self.zones = zones
        self.procedure = procedure
        self.vision_config = vision_config
        self._tracker_factory = tracker_factory
        self._clock = clock
        engine = ConformanceEngine()
        self.emitter = PhysicalEventEmitter(zones, procedure.procedure_id, vision_config)          # M1
        self.pipeline = PerceptionPipeline(zones, self.emitter, procedure, engine, tracker=None)    # M1
        self.coordinator = DualChannelCoordinator(procedure, engine)                                # M2
        self.persons: list[PersonView] = []
        self.frame_size: tuple[int, int] | None = None
        self.frame_seq = 0
        self.last_frame_at: datetime | None = None
        self.notice: str | None = None
        self.vision_status = "idle"          # idle | loading | ready | unavailable
        self.vision_message = "Camera analysis starts when the first frame arrives."
        self.closed = False

    # ---- vision -----------------------------------------------------------------
    def ensure_tracker(self) -> None:
        if self.pipeline.tracker is not None or self.vision_status == "unavailable":
            return
        self.vision_status, self.vision_message = "loading", "Loading the person-detection model…"
        try:
            self.pipeline.tracker = self._tracker_factory(self.vision_config)
        except MissingDependencyError as exc:
            self.vision_status, self.vision_message = "unavailable", str(exc)
        except VisionError as exc:
            log.error("vision model failed to load: %s", exc)
            self.vision_status = "unavailable"
            self.vision_message = "The person-detection model could not be loaded. See the backend console."
        except Exception:  # noqa: BLE001 - never leak internals to the client
            log.exception("vision model failed to load")
            self.vision_status = "unavailable"
            self.vision_message = "The person-detection model could not be loaded. See the backend console."
        else:
            self.vision_status, self.vision_message = "ready", "Person detection active."

    def process_jpeg(self, data: bytes) -> None:
        """Analyse one browser frame through the existing M1 pipeline and feed new events to M2."""
        image = decode_jpeg(data)
        self.ensure_tracker()
        if self.pipeline.tracker is None:
            raise ProtocolError("vision_unavailable", self.vision_message)
        now = self._clock()
        try:
            result = self.pipeline.process_frame(image, now)
        except VisionError as exc:
            log.warning("frame analysis failed: %s", exc)
            raise ProtocolError("analysis_failed", "Frame analysis failed on the backend; the frame was skipped.") from None
        self.frame_size = (int(image.shape[1]), int(image.shape[0]))
        self.frame_seq += 1
        self.last_frame_at = now
        self.persons = list(result.persons)
        if result.new_events:
            try:
                self.coordinator.add_physical_events(result.new_events)
            except DualChannelError as exc:
                self.notice = str(exc)

    # ---- commands (same semantics as the M2/M3 keyboard controls) -------------------
    def apply(self, command: Command) -> tuple[bool, str]:
        name = command.name
        try:
            if name == "reset":
                self.pipeline.reset()
                self.coordinator.reset()
                self.persons = []
                self.notice = None
                return True, RESET_TEXT
            if command.preset_id is not None:
                preset = PRESETS[command.preset_id]
                self.coordinator.inject_digital_preset(preset)
                return True, f"SIMULATED digital injected: {preset.title}"
            if name == "digital_clear":
                self.coordinator.clear_digital()
                return True, CLEAR_TEXT
        except DuplicateInjectionError:
            return False, DUPLICATE_TEXT
        except NoActiveJourneyError:
            return False, "No journey yet. Enter Zone A to begin a journey."
        except DualChannelError as exc:
            return False, str(exc)
        if name in COMMANDS:
            return True, name
        return False, "unknown command"

    # ---- outputs ----------------------------------------------------------------
    def zones_payload(self) -> list[dict]:
        return [{"zone_id": z.zone_id, "name": z.name, "x1": z.x1, "y1": z.y1, "x2": z.x2, "y2": z.y2}
                for z in self.zones]

    def state(self) -> dict:
        coord = self.coordinator
        model = build_dashboard_model(coord, self.persons, timeline_limit=config.TIMELINE_LIMIT)
        active = coord.active_journey_id
        result = coord.result() if active else None
        focus = next((p for p in self.persons if active and p.journey_id == active), None) or \
            (self.persons[0] if self.persons else None)
        digital_events = coord.digital_events() if active else []
        return {
            "type": "state",
            "protocol": config.PROTOCOL_VERSION,
            "session_id": self.session_id,
            "journey_id": active,
            "frame": ({"width": self.frame_size[0], "height": self.frame_size[1], "seq": self.frame_seq}
                      if self.frame_size else None),
            "vision": {"status": self.vision_status, "message": self.vision_message},
            "detections": [{
                "tracker_id": p.tracker_id,
                "confidence": round(float(p.confidence), 4),
                "box": [round(float(v), 5) for v in p.box],     # normalized x1, y1, x2, y2 of the analysed frame
                "zone_id": p.zone_id,
                "in_active_journey": bool(active and p.journey_id == active),
            } for p in self.persons],
            "zones": self.zones_payload(),
            "active_zone": focus.zone_id if focus else None,
            "expected": [{"step_id": sid, "name": nm} for sid, nm in model.expected],
            "physical_trace": list(model.physical_trace),
            "digital_trace": [{"step_id": sid, "failed": failed} for sid, failed in model.digital_trace],
            "step_states": [{"step_id": s.step_id, "name": s.name, "state": s.state,
                             "indicator": s.indicator, "word": s.word} for s in model.steps],
            "verdict": model.verdict,                      # WAITING | IN PROGRESS | COMPLETED | VIOLATED | UNCERTAIN
            "engine_status": result.overall_status.value if result else None,
            "violation_types": [v.type.value for v in result.violations] if result else [],
            "violation_labels": list(model.violation_labels),
            "finding": model.primary_finding,
            "finding_where": model.verdict_where,
            "extra_findings": model.extra_findings,
            "timeline": [_timeline_dict(t) for t in model.timeline],
            "digital_active": bool(digital_events),
            "digital_simulated": True,
            "notice": self.notice,
            "disclosures": disclosures(),
        }

    def evidence(self) -> dict:
        """Structured evidence of the active journey (M3 export + full timeline). No images, no identity."""
        if self.coordinator.active_journey_id is None:
            raise NoActiveJourneyError("Nothing to save yet: no journey. Enter Zone A first.")
        evidence = build_evidence(self.coordinator)
        names = labels.step_names(self.procedure)
        evidence["timeline"] = [_timeline_dict(t) for t in build_timeline(
            self.coordinator.physical_events(), self.coordinator.digital_events(), names, limit=10_000)]
        evidence["export"] = {"source": "m6.1-web-dashboard", "protocol": config.PROTOCOL_VERSION,
                              "frames_saved": False, "image_file": None}
        evidence["disclosures"] = disclosures()
        return evidence

    def close(self) -> None:
        """Forget everything this session held (journeys, both channels, tracks)."""
        self.closed = True
        try:
            self.pipeline.reset()
        except Exception:  # noqa: BLE001
            pass
        self.coordinator.reset()
        self.pipeline.tracker = None
        self.persons = []


def _timeline_dict(t) -> dict:
    return {
        "event_id": t.event_id,
        "timestamp": t.timestamp.astimezone(timezone.utc).isoformat(),
        "channel": t.channel,
        "step_id": t.step_id,
        "step_name": t.step_name,
        "event_type": t.event_text,
        "confidence": None if t.confidence is None else round(float(t.confidence), 4),
        "simulated": t.simulated,
    }


def disclosures() -> dict:
    return {
        "digital_label": labels.SIM_LABEL,
        "digital_note": config.SIM_NOTE,
        "digital_long": labels.SIM_DISCLAIMER_LONG,
        "privacy": labels.PRIVACY_FOOTER,
        "frames": config.FRAMES_NOTE,
        "frames_storage": config.FRAMES_STORAGE_NOTE,
    }


class SessionLimitError(Exception):
    pass


class SessionManager:
    """Holds the isolated sessions. Removing a session drops all of its state."""

    def __init__(self, zones: ZoneSet, procedure: ProcedureDefinition, vision_config: VisionConfig | None = None,
                 tracker_factory: TrackerFactory = default_tracker_factory, clock: Clock = _utc_now,
                 max_sessions: int = config.MAX_SESSIONS):
        self.zones, self.procedure = zones, procedure
        self.vision_config = vision_config or VisionConfig(mirror=False)  # the browser mirrors; backend never flips
        self.vision_config.validate()
        self.tracker_factory, self.clock, self.max_sessions = tracker_factory, clock, max_sessions
        self._sessions: dict[str, WebSession] = {}
        self._lock = threading.Lock()

    def create(self) -> WebSession:
        with self._lock:
            if len(self._sessions) >= self.max_sessions:
                raise SessionLimitError(f"At most {self.max_sessions} concurrent web sessions are allowed.")
            sid = str(uuid.uuid4())
            s = WebSession(sid, self.zones, self.procedure, self.vision_config, self.tracker_factory, self.clock)
            self._sessions[sid] = s
            return s

    def get(self, session_id: str) -> WebSession | None:
        return self._sessions.get(session_id)

    def remove(self, session_id: str) -> None:
        with self._lock:
            s = self._sessions.pop(session_id, None)
        if s is not None:
            s.close()

    @property
    def count(self) -> int:
        return len(self._sessions)

    @property
    def session_ids(self) -> list[str]:
        return list(self._sessions)
