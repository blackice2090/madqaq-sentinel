"""Camera-free tests for dwell confirmation, smoothing, hysteresis and step de-duplication."""
from datetime import datetime, timedelta, timezone

import pytest

from sentinel.domain.models import ViolationType
from sentinel.vision.config import VisionConfig, VisionError
from sentinel.vision.event_emitter import PhysicalEventEmitter
from sentinel.vision.pipeline import PerceptionPipeline
from sentinel.vision.tracker import TrackedPerson
from sentinel.vision.zones import ZoneSet
from simulator.scenarios import procedure

T0 = datetime(2026, 10, 17, 12, 0, 0, tzinfo=timezone.utc)
X = {"A": 0.13, "B": 0.38, "C": 0.63, "D": 0.87}


def person(x, tid=1, conf=0.9):
    return TrackedPerson(tid, conf, (x - 0.03, 0.2, x + 0.03, 0.95))


@pytest.fixture
def zones():
    return ZoneSet.load("config/checkpoint_zones.json")


def make(zones, **kw):
    kw.setdefault("zone_dwell_ms", 600.0)
    kw.setdefault("smoothing_window", 1)
    kw.setdefault("boundary_margin", 0.0)
    kw.setdefault("min_consecutive_frames", 1)
    return PhysicalEventEmitter(zones, "generic-checkpoint-v1", VisionConfig(**kw))


class Feeder:
    """Feeds frames at a fixed frame interval on a shared millisecond clock."""

    def __init__(self, em, step_ms=100):
        self.em, self.step, self.ms, self.events = em, step_ms, 0, []

    def hold(self, x, duration_ms, tid=1):
        for _ in range(int(duration_ms // self.step)):
            self.frame(x, tid)

    def frame(self, x, tid=1):
        self.events += self.em.process([person(x, tid)], T0 + timedelta(milliseconds=self.ms))
        self.ms += self.step

    @property
    def trace(self):
        return [e.step_id for e in self.events]


def enter_a(f):
    f.hold(X["A"], 800)


# 1. single-frame B entry emits nothing before dwell
def test_single_frame_b_emits_nothing(zones):
    f = Feeder(make(zones)); enter_a(f)
    f.frame(X["B"])
    assert f.trace == ["A"]


def test_b_held_below_dwell_emits_nothing(zones):
    f = Feeder(make(zones)); enter_a(f)
    f.hold(X["B"], 500)  # 5 frames, 400 ms elapsed between first and last
    assert f.trace == ["A"]


# 2. stable B beyond dwell emits exactly one B
def test_stable_b_emits_exactly_one_event(zones):
    f = Feeder(make(zones)); enter_a(f)
    f.hold(X["B"], 3000)
    assert f.trace == ["A", "B"]


def test_dwell_is_time_based_not_frame_based(zones):
    # many frames inside a short time must NOT confirm a zone
    em = make(zones, min_consecutive_frames=3)
    ev = []
    for i in range(10):
        ev += em.process([person(X["A"])], T0 + timedelta(milliseconds=i * 10))  # 100 ms total
    assert ev == []
    ev += em.process([person(X["A"])], T0 + timedelta(milliseconds=650))
    assert [e.step_id for e in ev] == ["A"]


# 3. boundary jitter without satisfying dwell emits nothing extra
def test_jitter_between_b_and_c_emits_nothing(zones):
    f = Feeder(make(zones)); enter_a(f)
    for _ in range(30):
        f.frame(X["B"]); f.frame(X["C"])
    assert f.trace == ["A"]


def test_candidate_timer_restarts_when_candidate_changes(zones):
    f = Feeder(make(zones)); enter_a(f)
    f.hold(X["B"], 500); f.hold(X["C"], 300); f.hold(X["B"], 500)  # B never held 600 ms in a row
    assert f.trace == ["A"]


# 4. B re-entry after B emitted does not emit B again
def test_b_reentry_does_not_emit_again(zones):
    f = Feeder(make(zones)); enter_a(f)
    f.hold(X["B"], 800); f.hold(X["C"], 800); f.hold(X["B"], 800)
    assert f.trace == ["A", "B", "C"]


# 5. A,B,C,B,C,D,C,D -> A,B,C,D
def test_jittery_walk_emits_clean_trace(zones):
    f = Feeder(make(zones))
    for z in "ABCBCDCD":
        f.hold(X[z], 800)
    assert f.trace == ["A", "B", "C", "D"]
    assert len(f.events) == 4
    assert len({e.journey_id for e in f.events}) == 1


# 6. first-visit order is preserved: A,C,B stays A,C,B (never sorted)
def test_first_visit_order_preserved_a_c_b(zones):
    f = Feeder(make(zones))
    for z in "ACB":
        f.hold(X[z], 800)
    assert f.trace == ["A", "C", "B"]


def test_a_c_b_reaches_m0_as_order_inversion(zones):
    em = make(zones)
    pipe = PerceptionPipeline(zones, em, procedure())
    f = Feeder(em)
    for z in "ACB":
        f.hold(X[z], 800)
    result = pipe.evaluate(next(iter(em.journeys)))
    assert result.violations[0].type == ViolationType.ORDER_INVERSION
    assert result.violations[0].step_id == "B"


def test_a_c_d_still_reaches_m0_as_omission(zones):
    em = make(zones)
    pipe = PerceptionPipeline(zones, em, procedure())
    f = Feeder(em)
    for z in "ACD":
        f.hold(X[z], 800)
    v = pipe.evaluate(next(iter(em.journeys))).violations[0]
    assert (v.type, v.step_id) == (ViolationType.OMISSION, "B")


# 7. reset clears emitted-step suppression and smoothing state
def test_reset_clears_suppression_and_smoothing(zones):
    em = make(zones, smoothing_window=5)
    f = Feeder(em)
    for z in "AB":
        f.hold(X[z], 1200)  # median-5 lags a hard jump by ~3 frames, so hold longer than dwell
    assert f.trace == ["A", "B"]
    old_journey = next(iter(em.journeys))
    em.reset()
    assert em.journeys == {} and em.debug_for_tracker(1) is None
    # smoothing history is gone: first frame after reset is exactly the raw point
    em.process([person(0.40)], T0 + timedelta(seconds=60))
    assert em.debug_for_tracker(1).smoothed_point[0] == pytest.approx(0.40)
    # emitted-step suppression is gone: A and B are emitted again for a NEW journey
    f2 = Feeder(em); f2.ms = 120_000
    for z in "AB":
        f2.hold(X[z], 1200)
    assert f2.trace == ["A", "B"]
    assert next(iter(em.journeys)) != old_journey


# 8. smoothing reduces one-frame spikes
def test_smoothing_suppresses_single_frame_spike(zones):
    em = make(zones, smoothing_window=5)
    series = []
    for i, x in enumerate([0.13, 0.13, 0.13, 0.13, 0.63, 0.13, 0.13]):  # spike into zone C
        em.process([person(x)], T0 + timedelta(milliseconds=i * 100))
        series.append(em.debug_for_tracker(1))
    raw_jump = max(abs(a.raw_point[0] - b.raw_point[0]) for a, b in zip(series, series[1:]))
    smooth_jump = max(abs(a.smoothed_point[0] - b.smoothed_point[0]) for a, b in zip(series, series[1:]))
    assert raw_jump == pytest.approx(0.5)
    assert smooth_jump < 0.05
    assert series[4].raw_zone == "C" and series[4].candidate_zone == "A"


def test_smoothing_window_one_is_raw(zones):
    em = make(zones, smoothing_window=1)
    em.process([person(0.13)], T0)
    em.process([person(0.63)], T0 + timedelta(milliseconds=100))
    assert em.debug_for_tracker(1).smoothed_point[0] == pytest.approx(0.63)


# hysteresis / deadband
def test_boundary_margin_keeps_stable_zone_near_edge(zones):
    em = make(zones, boundary_margin=0.02)
    f = Feeder(em); f.hold(X["A"], 800)
    f.hold(0.25, 2000)  # just outside A (x2=0.24) but inside the 0.02 deadband
    assert em.debug_for_tracker(1).stable_zone == "A"
    assert em.debug_for_tracker(1).candidate_zone == "A"


def test_leaving_beyond_margin_starts_candidate_none(zones):
    em = make(zones, boundary_margin=0.02)
    f = Feeder(em); f.hold(X["A"], 800)
    f.frame(0.265)  # beyond A+margin (0.26), still in the gap before B (0.27)
    d = em.debug_for_tracker(1)
    assert d.candidate_zone is None and d.stable_zone == "A"


def test_margin_does_not_make_neighbouring_zone_ambiguous(zones):
    em = make(zones, boundary_margin=0.02)
    f = Feeder(em); f.hold(X["A"], 800)
    f.hold(0.275, 800)  # clearly inside B and beyond A's deadband
    assert f.trace == ["A", "B"]


def test_zone_dwell_default_and_validation():
    c = VisionConfig()
    assert c.zone_dwell_ms == 600 and c.smoothing_window == 5 and c.boundary_margin == pytest.approx(0.02)
    for bad in ({"zone_dwell_ms": -1}, {"smoothing_window": 0}, {"boundary_margin": 0.5}, {"boundary_margin": -0.1}):
        with pytest.raises(VisionError):
            VisionConfig(**bad).validate()


def test_debug_snapshot_fields(zones):
    em = make(zones)
    em.process([person(X["A"])], T0)
    d = em.debug_for_tracker(1)
    assert (d.raw_zone, d.candidate_zone, d.stable_zone) == ("A", "A", None)
    assert d.dwell_target_ms == 600 and d.dwell_ms == 0
    assert d.smoothed_point == pytest.approx((X["A"], 0.95))
