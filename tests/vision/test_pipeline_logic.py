from datetime import datetime, timedelta, timezone

import pytest

from sentinel.domain.models import JourneyStatus, ViolationType
from sentinel.vision.config import VisionConfig
from sentinel.vision.event_emitter import PhysicalEventEmitter
from sentinel.vision.pipeline import PerceptionPipeline, physical_trace
from sentinel.vision.tracker import TrackedPerson
from sentinel.vision.zones import ZoneSet
from simulator.scenarios import procedure

T0 = datetime(2026, 10, 17, 12, 0, 0, tzinfo=timezone.utc)
X = {"A": 0.13, "B": 0.38, "C": 0.63, "D": 0.87}


def person(zone, tid=1, conf=0.9):
    x = X[zone]
    return TrackedPerson(tid, conf, (x - 0.03, 0.2, x + 0.03, 0.95))


@pytest.fixture
def pipe():
    zones = ZoneSet.load("config/checkpoint_zones.json")
    proc = procedure()
    em = PhysicalEventEmitter(zones, proc.procedure_id, VisionConfig(min_consecutive_frames=1, zone_dwell_ms=0.0, smoothing_window=1, boundary_margin=0.0))
    return PerceptionPipeline(zones, em, proc)


def run(pipe, steps, tid=1):
    t = T0
    jid = None
    for z in steps:
        t += timedelta(seconds=2)
        res = pipe.process_persons([person(z, tid)], t)
        jid = jid or (res.persons[0].journey_id)
    return jid


def test_full_physical_walk_is_uncertain_not_completed(pipe):
    jid = run(pipe, "ABCD")
    result = pipe.evaluate(jid)
    assert result.violations == []
    assert result.overall_status == JourneyStatus.UNCERTAIN  # single channel is never CONFIRMED
    s = pipe.summarize(jid)
    assert s.headline == "PHYSICAL TRACE COMPLETE"
    assert s.reason == "awaiting digital-channel confirmation"
    assert s.m0_status == JourneyStatus.UNCERTAIN
    assert s.trace == ["A", "B", "C", "D"]


def test_skipping_b_yields_step_specific_omission(pipe):
    jid = run(pipe, "ACD")
    result = pipe.evaluate(jid)
    assert result.overall_status == JourneyStatus.VIOLATED
    assert result.violations[0].type == ViolationType.OMISSION
    assert result.violations[0].step_id == "B"
    s = pipe.summarize(jid)
    assert s.headline == "VIOLATED"
    assert "Missing step: B" in s.violation_lines


def test_in_progress_trace_is_not_reported_complete(pipe):
    jid = run(pipe, "AB")
    s = pipe.summarize(jid)
    assert s.headline == "PHYSICAL TRACE IN PROGRESS"
    assert s.trace == ["A", "B"]
    assert s.m0_status == JourneyStatus.UNCERTAIN


def test_out_of_order_walk_reports_order_inversion(pipe):
    jid = run(pipe, "ACB")
    assert pipe.evaluate(jid).violations[0].type == ViolationType.ORDER_INVERSION


def test_no_digital_evidence_is_fabricated(pipe):
    jid = run(pipe, "ABCD")
    from sentinel.domain.models import EvidenceSource
    assert all(e.source == EvidenceSource.PHYSICAL for e in pipe.emitter.all_events())
    # the engine only ever receives what the caller passes in: nothing by default
    seen = {}
    real = pipe.engine.evaluate

    def spy(proc, journey, physical, digital):
        seen["digital"] = digital
        return real(proc, journey, physical, digital)

    pipe.engine.evaluate = spy
    pipe.evaluate(jid)
    assert seen["digital"] == []


def test_frame_result_reports_new_events_once(pipe):
    first = pipe.process_persons([person("A")], T0)
    again = pipe.process_persons([person("A")], T0 + timedelta(seconds=1))
    assert [e.step_id for e in first.new_events] == ["A"]
    assert again.new_events == []
    assert first.persons[0].zone_id == "A"


def test_late_tracker_in_c_has_no_journey_view(pipe):
    res = pipe.process_persons([person("C", tid=9)], T0)
    assert res.new_events == []
    assert res.persons[0].journey_id is None
    assert pipe.focus_journey_id() is None


def test_focus_journey_is_most_recent(pipe):
    pipe.process_persons([person("A", 1)], T0)
    pipe.process_persons([person("A", 1), person("A", 2)], T0 + timedelta(seconds=5))
    assert pipe.focus_journey_id() == pipe.emitter.journey_for_tracker(2)


def test_reset_clears_everything(pipe):
    run(pipe, "ABC")
    pipe.reset()
    assert pipe.emitter.journeys == {}
    assert pipe.focus_journey_id() is None


def test_physical_trace_collapses_consecutive_duplicates(pipe):
    run(pipe, "AABBC")
    rec = next(iter(pipe.emitter.journeys.values()))
    assert physical_trace(rec.events) == ["A", "B", "C"]


def test_zones_must_match_procedure_steps():
    zones = ZoneSet.from_dict({"Z": {"name": "z", "x1": 0, "y1": 0, "x2": 1, "y2": 1}})
    proc = procedure()
    em = PhysicalEventEmitter(zones, proc.procedure_id, VisionConfig(entry_zone_id="Z"))
    with pytest.raises(ValueError):
        PerceptionPipeline(zones, em, proc)
