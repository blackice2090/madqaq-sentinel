"""Camera-free fixtures. Physical events come from the real M1 emitter fed with synthetic
tracker positions (no camera, no model); digital events come from the M2 simulator."""
from datetime import datetime, timedelta, timezone

import pytest

from sentinel.digital.simulator import DigitalEventSimulator
from sentinel.dual_channel import DualChannelCoordinator
from sentinel.vision.config import VisionConfig
from sentinel.vision.event_emitter import PhysicalEventEmitter
from sentinel.vision.tracker import TrackedPerson
from sentinel.vision.zones import ZoneSet
from simulator.scenarios import procedure as make_procedure

T0 = datetime(2026, 10, 17, 12, 0, 0, tzinfo=timezone.utc)
X = {"A": 0.13, "B": 0.38, "C": 0.63, "D": 0.87}


@pytest.fixture
def procedure():
    return make_procedure()


@pytest.fixture
def coordinator(procedure):
    clock = lambda: datetime(2026, 10, 17, 12, 5, 0, tzinfo=timezone.utc)  # noqa: E731
    return DualChannelCoordinator(procedure, simulator=DigitalEventSimulator(clock=clock))


@pytest.fixture
def walk(procedure):
    """walk("ACD") -> PHYSICAL events from a fresh M1 emitter (new anonymous journey id each call)."""
    zones = ZoneSet.load("config/checkpoint_zones.json")

    def _walk(steps: str, tracker_id: int = 1):
        em = PhysicalEventEmitter(zones, procedure.procedure_id, VisionConfig())
        events, ms = [], 0
        for z in steps:
            for _ in range(15):  # 1.5 s per zone at 10 fps: well past dwell + smoothing lag
                x = X[z]
                events += em.process([TrackedPerson(tracker_id, 0.9, (x - 0.03, 0.2, x + 0.03, 0.95))],
                                     T0 + timedelta(milliseconds=ms))
                ms += 100
        assert [e.step_id for e in events] == list(steps), "fixture must reproduce the requested physical trace"
        return events

    return _walk
