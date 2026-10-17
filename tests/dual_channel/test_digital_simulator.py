import uuid
from datetime import datetime, timedelta, timezone

import pytest

from sentinel.digital import B_FAILED, FULL_TRACE, PRESETS, PRESETS_BY_KEY, SIMULATOR_SOURCE, WITHOUT_B, DigitalEventSimulator
from sentinel.domain.models import EventType, EvidenceSource

NOW = datetime(2026, 10, 17, 12, 5, 0, tzinfo=timezone.utc)
PROC = "generic-checkpoint-v1"


@pytest.fixture
def sim():
    return DigitalEventSimulator(clock=lambda: NOW)


# 3. simulator events are DIGITAL
@pytest.mark.parametrize("preset", list(PRESETS.values()))
def test_events_are_digital(sim, preset):
    events = sim.build_events(preset, "J-1", PROC)
    assert events and all(e.source == EvidenceSource.DIGITAL for e in events)


# 4. same journey/procedure as given
def test_events_bind_to_given_journey_and_procedure(sim):
    events = sim.build_events(FULL_TRACE, "J-live-123", PROC)
    assert {e.journey_id for e in events} == {"J-live-123"}
    assert {e.procedure_id for e in events} == {PROC}


def test_completed_and_failed_event_types(sim):
    ok = sim.build_events(FULL_TRACE, "J", PROC)
    assert [e.event_type for e in ok] == [EventType.STEP_COMPLETED] * 4
    bad = sim.build_events(B_FAILED, "J", PROC)
    assert [(e.step_id, e.event_type) for e in bad] == [
        ("A", EventType.STEP_COMPLETED), ("B", EventType.STEP_FAILED),
        ("C", EventType.STEP_COMPLETED), ("D", EventType.STEP_COMPLETED)]


def test_presets_have_expected_steps():
    assert [s for s, _ in FULL_TRACE.steps] == ["A", "B", "C", "D"]
    assert [s for s, _ in WITHOUT_B.steps] == ["A", "C", "D"]
    assert [(s, ok) for s, ok in B_FAILED.steps if s == "B"] == [("B", False)]
    assert {k: p.preset_id for k, p in PRESETS_BY_KEY.items()} == {"1": "full_trace", "2": "without_b", "3": "b_failed"}


# 17. metadata says simulated
def test_metadata_marks_events_as_simulated(sim):
    for e in sim.build_events(FULL_TRACE, "J", PROC):
        assert e.metadata == {"source": "m2_digital_simulator", "simulated": True}
        assert e.metadata["source"] == SIMULATOR_SOURCE and e.metadata["simulated"] is True


def test_uuid_event_ids_unique(sim):
    ids = [e.event_id for e in sim.build_events(FULL_TRACE, "J", PROC) + sim.build_events(FULL_TRACE, "J", PROC)]
    assert len(set(ids)) == 8
    for i in ids:
        assert str(uuid.UUID(i)) == i


# 16. timestamps aware, ordered, not in the future, and order survives the engine's (timestamp, id) sort
def test_timestamps_aware_increasing_not_future(sim):
    events = sim.build_events(FULL_TRACE, "J", PROC)
    ts = [e.timestamp for e in events]
    assert all(t.tzinfo is not None and t.utcoffset() == timedelta(0) for t in ts)
    assert ts == sorted(ts) and len(set(ts)) == len(ts)
    assert max(ts) <= NOW


def test_preset_order_survives_engine_sorting(sim):
    for _ in range(25):  # random UUIDs must never reorder the trace
        events = sim.build_events(FULL_TRACE, "J", PROC)
        assert [e.step_id for e in sorted(events, key=lambda e: (e.timestamp, e.event_id))] == ["A", "B", "C", "D"]


def test_naive_clock_rejected():
    with pytest.raises(ValueError):
        DigitalEventSimulator(clock=lambda: datetime(2026, 1, 1)).build_events(FULL_TRACE, "J", PROC)


def test_invalid_step_ms():
    with pytest.raises(ValueError):
        DigitalEventSimulator(step_ms=0)


# 18. no identity
def test_no_identity_fields(sim):
    for e in sim.build_events(FULL_TRACE, "J", PROC):
        text = str(e.model_dump()).lower()
        assert not any(b in text for b in ("face", "biometric", "identity", "embedding", "name"))
