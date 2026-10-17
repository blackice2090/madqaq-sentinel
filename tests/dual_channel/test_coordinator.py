from datetime import timedelta

import pytest

from sentinel.digital import FULL_TRACE
from sentinel.domain.models import EventType, EvidenceSource, JourneyStatus, NormalizedEvent
from sentinel.dual_channel import (
    DuplicateInjectionError, EvidenceValidationError, JourneyMismatchError, NoActiveJourneyError,
)
from sentinel.dual_channel.coordinator import NO_JOURNEY_MESSAGE


# 1. separate empty physical and digital lists
def test_starts_with_no_journey_and_separate_channels(coordinator, walk):
    assert coordinator.active_journey_id is None
    assert coordinator.journey_ids == []
    with pytest.raises(NoActiveJourneyError):
        coordinator.physical_events()
    coordinator.add_physical_events(walk("A"))
    assert len(coordinator.physical_events()) == 1
    assert coordinator.digital_events() == []
    assert coordinator.physical_events() is not coordinator.digital_events()


def test_returned_lists_are_copies(coordinator, walk):
    coordinator.add_physical_events(walk("A"))
    coordinator.physical_events().clear()
    assert len(coordinator.physical_events()) == 1


# 2. physical events remain PHYSICAL
def test_physical_events_stay_physical_and_unmodified(coordinator, walk):
    events = walk("ABC")
    coordinator.add_physical_events(events)
    stored = coordinator.physical_events()
    assert stored == events  # exact events, exact timestamps, exact order
    assert all(e.source == EvidenceSource.PHYSICAL for e in stored)
    assert coordinator.digital_events() == []


def test_physical_arrival_order_is_never_sorted(coordinator, walk):
    events = walk("ACB")
    coordinator.add_physical_events(events)
    assert [e.step_id for e in coordinator.physical_events()] == ["A", "C", "B"]
    assert coordinator.summary().physical_trace == ["A", "C", "B"]


# 5. injection without an active journey is rejected cleanly
def test_digital_injection_without_journey_is_rejected(coordinator):
    with pytest.raises(NoActiveJourneyError) as exc:
        coordinator.inject_digital_preset(FULL_TRACE)
    assert str(exc.value) == "Enter Zone A to begin a journey before injecting digital evidence."
    assert str(exc.value) == NO_JOURNEY_MESSAGE
    assert coordinator.active_journey_id is None and coordinator.journey_ids == []  # no fake journey


def test_digital_events_without_journey_rejected(coordinator, walk):
    other = walk("A")
    from sentinel.digital import DigitalEventSimulator
    digital = DigitalEventSimulator().build_events(FULL_TRACE, other[0].journey_id, other[0].procedure_id)
    with pytest.raises(NoActiveJourneyError):
        coordinator.add_digital_events(digital)


# 6. reset clears both channels
def test_reset_clears_both_channels(coordinator, walk):
    coordinator.add_physical_events(walk("ABCD"))
    coordinator.inject_digital_preset(FULL_TRACE)
    coordinator.reset()
    assert coordinator.active_journey_id is None and coordinator.journey_ids == []
    with pytest.raises(NoActiveJourneyError):
        coordinator.digital_events()
    with pytest.raises(NoActiveJourneyError):
        coordinator.inject_digital_preset(FULL_TRACE)


# 7. a new journey cannot see old digital events
def test_new_journey_does_not_inherit_digital_evidence(coordinator, walk):
    first = walk("ABCD")
    coordinator.add_physical_events(first)
    coordinator.inject_digital_preset(FULL_TRACE)
    old_id = coordinator.active_journey_id
    second = walk("A")
    coordinator.add_physical_events(second)
    new_id = coordinator.active_journey_id
    assert new_id != old_id
    assert coordinator.digital_events(new_id) == []
    assert all(e.journey_id == new_id for e in coordinator.physical_events(new_id))
    assert len(coordinator.digital_events(old_id)) == 4  # old journey keeps its own evidence
    assert coordinator.summary().digital_trace == []
    # the new journey can receive its own preset (injection state is per journey)
    coordinator.inject_digital_preset(FULL_TRACE)
    assert all(e.journey_id == new_id for e in coordinator.digital_events(new_id))


def test_digital_events_for_old_journey_rejected(coordinator, walk):
    first = walk("A")
    coordinator.add_physical_events(first)
    coordinator.add_physical_events(walk("A"))  # now active
    from sentinel.digital import DigitalEventSimulator
    stale = DigitalEventSimulator().build_events(FULL_TRACE, first[0].journey_id, first[0].procedure_id)
    with pytest.raises(JourneyMismatchError):
        coordinator.add_digital_events(stale)
    assert coordinator.digital_events() == []


# 8. duplicate preset injection is suppressed
def test_duplicate_preset_injection_is_suppressed(coordinator, walk):
    coordinator.add_physical_events(walk("ABCD"))
    coordinator.inject_digital_preset(FULL_TRACE)
    before = coordinator.digital_events()
    with pytest.raises(DuplicateInjectionError):
        coordinator.inject_digital_preset(FULL_TRACE)
    assert coordinator.digital_events() == before and len(before) == 4


def test_second_different_preset_also_blocked_until_cleared(coordinator, walk):
    coordinator.add_physical_events(walk("ABCD"))
    coordinator.inject_digital_preset("1")
    with pytest.raises(DuplicateInjectionError):
        coordinator.inject_digital_preset("2")
    coordinator.clear_digital()
    assert coordinator.digital_events() == []
    coordinator.inject_digital_preset("2")  # allowed again after an explicit clear
    assert [e.step_id for e in coordinator.digital_events()] == ["A", "C", "D"]


def test_clear_digital_leaves_physical_untouched(coordinator, walk):
    coordinator.add_physical_events(walk("ABCD"))
    coordinator.inject_digital_preset(FULL_TRACE)
    coordinator.clear_digital()
    assert len(coordinator.physical_events()) == 4
    assert coordinator.result().overall_status == JourneyStatus.UNCERTAIN


# validation / error handling
def test_unknown_preset_rejected(coordinator, walk):
    coordinator.add_physical_events(walk("A"))
    with pytest.raises(EvidenceValidationError):
        coordinator.inject_digital_preset("nope")


def test_invalid_digital_step_id_rejected(coordinator, walk):
    coordinator.add_physical_events(walk("A"))
    jid = coordinator.active_journey_id
    bad = NormalizedEvent(event_id="x", journey_id=jid, procedure_id="generic-checkpoint-v1", source=EvidenceSource.DIGITAL,
                          event_type=EventType.STEP_COMPLETED, step_id="Z", timestamp=coordinator.physical_events()[0].timestamp)
    with pytest.raises(EvidenceValidationError, match="Unknown step id 'Z'"):
        coordinator.add_digital_events([bad])
    assert coordinator.digital_events() == []


def test_digital_procedure_mismatch_rejected(coordinator, walk):
    coordinator.add_physical_events(walk("A"))
    e = coordinator.physical_events()[0]
    bad = e.model_copy(update={"event_id": "d1", "source": EvidenceSource.DIGITAL,
                               "event_type": EventType.STEP_COMPLETED, "procedure_id": "other-procedure"})
    with pytest.raises(EvidenceValidationError, match="procedure"):
        coordinator.add_digital_events([bad])


def test_digital_event_in_physical_channel_rejected(coordinator, walk):
    coordinator.add_physical_events(walk("A"))
    jid = coordinator.active_journey_id
    from sentinel.digital import DigitalEventSimulator
    digital = DigitalEventSimulator().build_events(FULL_TRACE, jid, "generic-checkpoint-v1")
    with pytest.raises(EvidenceValidationError, match="channels are kept separate"):
        coordinator.add_physical_events(digital)
    with pytest.raises(EvidenceValidationError, match="channels are kept separate"):
        coordinator.add_digital_events(coordinator.physical_events())


def test_batch_with_one_bad_event_adds_nothing(coordinator, walk):
    coordinator.add_physical_events(walk("A"))
    jid = coordinator.active_journey_id
    from sentinel.digital import DigitalEventSimulator
    events = DigitalEventSimulator().build_events(FULL_TRACE, jid, "generic-checkpoint-v1")
    events[2] = events[2].model_copy(update={"step_id": "Z"})
    with pytest.raises(EvidenceValidationError):
        coordinator.add_digital_events(events)
    assert coordinator.digital_events() == []


def test_exact_duplicate_delivery_ignored_conflicting_rejected(coordinator, walk):
    events = walk("A")
    coordinator.add_physical_events(events)
    coordinator.add_physical_events(events)  # redelivery
    assert len(coordinator.physical_events()) == 1
    clash = events[0].model_copy(update={"confidence": 0.1})
    with pytest.raises(EvidenceValidationError, match="Conflicting duplicate"):
        coordinator.add_physical_events([clash])


# 16. timestamps remain timezone-aware
def test_all_stored_timestamps_are_timezone_aware(coordinator, walk):
    coordinator.add_physical_events(walk("ABCD"))
    coordinator.inject_digital_preset(FULL_TRACE)
    for e in coordinator.physical_events() + coordinator.digital_events():
        assert e.timestamp.tzinfo is not None and e.timestamp.utcoffset() == timedelta(0)


# 18. no identity or biometric fields
def test_no_identity_or_biometric_fields(coordinator, walk):
    coordinator.add_physical_events(walk("ABCD"))
    coordinator.inject_digital_preset(FULL_TRACE)
    banned = ("face", "biometric", "embedding", "identity", "person_name", "national", "passport")
    for e in coordinator.physical_events() + coordinator.digital_events():
        text = str(e.model_dump()).lower()
        assert not any(b in text for b in banned)
        assert set(e.model_dump()) == {"event_id", "journey_id", "procedure_id", "source", "event_type",
                                       "step_id", "timestamp", "confidence", "metadata"}
