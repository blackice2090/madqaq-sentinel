from datetime import datetime, timedelta, timezone

import pytest

from sentinel.domain.models import EventType, EvidenceSource, NormalizedEvent
from sentinel.vision.config import VisionConfig
from sentinel.vision.event_emitter import PhysicalEventEmitter
from sentinel.vision.tracker import TrackedPerson
from sentinel.vision.zones import ZoneSet

T0 = datetime(2026, 10, 17, 12, 0, 0, tzinfo=timezone.utc)
PROC = "generic-checkpoint-v1"
# x-centre of each zone in config/checkpoint_zones.json; ground point y = 0.95
X = {"A": 0.13, "B": 0.38, "C": 0.63, "D": 0.87, "none": 0.255}


def person(zone, tid=1, conf=0.9):
    x = X[zone]
    return TrackedPerson(tid, conf, (x - 0.03, 0.2, x + 0.03, 0.95))


@pytest.fixture
def zones():
    return ZoneSet.load("config/checkpoint_zones.json")


def make(zones, **kw):
    # Legacy helper: dwell/smoothing/hysteresis off so these tests isolate emitter basics.
    kw.setdefault("zone_dwell_ms", 0.0)
    kw.setdefault("smoothing_window", 1)
    kw.setdefault("boundary_margin", 0.0)
    cfg = VisionConfig(min_consecutive_frames=kw.pop("min_frames", 1), **kw)
    return PhysicalEventEmitter(zones, PROC, cfg)


class Clock:
    def __init__(self):
        self.t = T0

    def tick(self, s=1.0):
        self.t += timedelta(seconds=s)
        return self.t


def walk(em, steps, tid=1, frames=3, clock=None):
    clock = clock or Clock()
    out = []
    for z in steps:
        for _ in range(frames):
            out += em.process([person(z, tid)], clock.tick(0.1))
        clock.tick(1.0)
    return out


# 3. A -> B -> C -> D
def test_full_walk_emits_a_b_c_d(zones):
    ev = walk(make(zones), "ABCD")
    assert [e.step_id for e in ev] == ["A", "B", "C", "D"]
    assert len({e.journey_id for e in ev}) == 1


# 4. A -> C -> D
def test_skip_emits_a_c_d(zones):
    ev = walk(make(zones), "ACD")
    assert [e.step_id for e in ev] == ["A", "C", "D"]


# 5. no duplicates while remaining in the same zone
def test_no_duplicate_events_while_inside_zone(zones):
    em = make(zones)
    c = Clock()
    ev = []
    for _ in range(200):
        ev += em.process([person("A")], c.tick(0.05))
    assert [e.step_id for e in ev] == ["A"]


# 6. tracker -> journey assignment starts at A
def test_journey_assigned_at_a(zones):
    em = make(zones)
    assert em.journey_for_tracker(1) is None
    em.process([person("A")], T0)
    jid = em.journey_for_tracker(1)
    assert jid is not None and jid in em.journeys
    assert em.journeys[jid].tracker_id == 1


def test_journey_ids_are_distinct_per_tracker(zones):
    em = make(zones)
    em.process([person("A", 1), person("A", 2)], T0)
    assert em.journey_for_tracker(1) != em.journey_for_tracker(2)


# 7. a tracker first seen at C does not silently create a normal journey
def test_tracker_first_seen_at_c_creates_no_journey(zones):
    em = make(zones)
    ev = walk(em, "CD")
    assert ev == []
    assert em.journeys == {}
    assert em.journey_for_tracker(1) is None


def test_late_tracker_that_then_enters_a_starts_journey_at_a(zones):
    em = make(zones)
    ev = walk(em, "CA")
    assert [e.step_id for e in ev] == ["A"]


# 8. reset clears temporary state
def test_reset_clears_state(zones):
    em = make(zones)
    walk(em, "AB")
    assert em.journeys and em.all_events()
    em.reset()
    assert em.journeys == {} and em.all_events() == []
    assert em.journey_for_tracker(1) is None
    # a fresh journey (new id) can start afterwards
    ev = walk(em, "A")
    assert [e.step_id for e in ev] == ["A"]


def test_journey_ids_do_not_repeat_after_reset(zones):
    em = make(zones)
    em.process([person("A")], T0)
    first = em.journey_for_tracker(1)
    em.reset()
    em.process([person("A")], T0)
    assert em.journey_for_tracker(1) != first


# 9. timestamps are timezone-aware
def test_event_timestamps_are_timezone_aware_utc(zones):
    ev = walk(make(zones), "ABCD")
    assert all(e.timestamp.tzinfo is not None and e.timestamp.utcoffset() == timedelta(0) for e in ev)


def test_default_clock_is_utc_aware(zones):
    ev = make(zones).process([person("A")])
    assert ev[0].timestamp.utcoffset() == timedelta(0)


def test_naive_now_rejected(zones):
    with pytest.raises(ValueError):
        make(zones).process([person("A")], datetime(2026, 1, 1))


# 10. events pass existing NormalizedEvent validation and carry the specified shape
def test_events_validate_and_have_expected_shape(zones):
    ev = walk(make(zones), "ABCD")
    for e in ev:
        NormalizedEvent.model_validate(e.model_dump())  # extra="forbid", tz check
        assert e.source == EvidenceSource.PHYSICAL
        assert e.event_type == EventType.STEP_OBSERVED
        assert e.procedure_id == PROC
        assert 0.0 <= e.confidence <= 1.0
        assert set(e.metadata) == {"tracker_id", "zone", "source"}
        assert e.metadata["zone"] == e.step_id
        assert e.metadata["source"] == "live_webcam"
        assert e.metadata["tracker_id"] == 1
    assert len({e.event_id for e in ev}) == len(ev)


def test_confidence_is_detector_confidence(zones):
    em = make(zones, min_frames=2)
    em.process([person("A", conf=0.6)], T0)
    ev = em.process([person("A", conf=0.8)], T0 + timedelta(seconds=0.1))
    assert ev[0].confidence == pytest.approx(0.7)


# debounce / cooldown / pruning
def test_min_consecutive_frames_filters_flicker(zones):
    em = make(zones, min_frames=3)
    c = Clock()
    ev = []
    for z in ["A", "A", "A", "B", "A", "B", "A", "B"]:  # B never held 3 frames
        ev += em.process([person(z)], c.tick(0.1))
    assert [e.step_id for e in ev] == ["A"]


def test_reentry_of_emitted_step_is_suppressed(zones):
    em = make(zones)
    c = Clock()
    ev = []
    for z in ["A", "B", "A"]:
        ev += em.process([person(z)], c.tick(0.5))
    assert [e.step_id for e in ev] == ["A", "B"]


def test_reentry_after_a_long_time_is_still_suppressed(zones):
    em = make(zones)
    c = Clock()
    ev = []
    for z, gap in [("A", 0.5), ("B", 0.5), ("A", 600.0)]:
        ev += em.process([person(z)], c.tick(gap))
    assert [e.step_id for e in ev] == ["A", "B"]


def test_leaving_all_zones_then_returning_does_not_repeat_step(zones):
    em = make(zones)
    c = Clock()
    ev = []
    for z in ["A", "none", "A"]:
        ev += em.process([person(z)], c.tick(1.0))
    assert [e.step_id for e in ev] == ["A"]


def test_stale_trackers_pruned_but_journey_kept(zones):
    em = make(zones, track_timeout_s=5.0)
    em.process([person("A")], T0)
    jid = em.journey_for_tracker(1)
    em.process([], T0 + timedelta(seconds=10))
    assert em.journey_for_tracker(1) is None
    assert jid in em.journeys and em.journeys[jid].current_zone is None


def test_entry_zone_must_exist(zones):
    with pytest.raises(ValueError):
        PhysicalEventEmitter(zones, PROC, VisionConfig(entry_zone_id="Z"))


def test_no_identity_fields_on_events(zones):
    ev = walk(make(zones), "A")[0]
    dumped = str(ev.model_dump()).lower()
    for banned in ("face", "embedding", "identity", "name"):
        assert banned not in dumped
