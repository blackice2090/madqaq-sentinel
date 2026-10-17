"""The five core M2 demonstrations, run through real M1 physical events + simulator + M0 engine."""
import pytest

from sentinel.digital import B_FAILED, FULL_TRACE, WITHOUT_B
from sentinel.domain.models import JourneyStatus, StepState, ViolationType


def run(coordinator, walk, physical, preset=None):
    coordinator.add_physical_events(walk(physical))
    if preset is not None:
        coordinator.inject_digital_preset(preset)
    return coordinator.result(), coordinator.summary()


# Scenario 1 / test 10 - full agreement -> COMPLETED
def test_scenario1_full_agreement_completed(coordinator, walk):
    result, s = run(coordinator, walk, "ABCD", FULL_TRACE)
    assert result.overall_status == JourneyStatus.COMPLETED
    assert result.violations == []
    assert all(st.state == StepState.CONFIRMED for st in result.step_states)
    assert (s.status, s.finding) == (JourneyStatus.COMPLETED, "Dual-channel evidence agrees.")
    assert s.physical_trace == s.digital_trace == ["A", "B", "C", "D"]


# Scenario 2 / test 12 - phantom completion
def test_scenario2_phantom_completion(coordinator, walk):
    result, s = run(coordinator, walk, "ACD", FULL_TRACE)
    assert result.overall_status == JourneyStatus.VIOLATED
    v = result.violations[0]
    assert (v.type, v.step_id) == (ViolationType.PHANTOM_COMPLETION, "B")
    assert s.finding_codes[0] == "PHANTOM_COMPLETION"
    assert "Digital completion for step B has no supporting physical evidence." in s.finding


# Scenario 3 / test 11 - omission
def test_scenario3_omission(coordinator, walk):
    result, s = run(coordinator, walk, "ACD", WITHOUT_B)
    assert result.overall_status == JourneyStatus.VIOLATED
    v = result.violations[0]
    assert (v.type, v.step_id) == (ViolationType.OMISSION, "B")
    assert "Required step B is missing" in s.finding
    assert dict(s.step_states)["B"] == StepState.INCOMPLETE


# Scenario 4 / test 13 - channel contradiction
def test_scenario4_channel_contradiction(coordinator, walk):
    result, s = run(coordinator, walk, "ABCD", B_FAILED)
    assert result.overall_status == JourneyStatus.VIOLATED
    v = result.violations[0]
    assert (v.type, v.step_id) == (ViolationType.CHANNEL_CONTRADICTION, "B")
    assert s.digital_trace == ["A", "B(FAILED)", "C", "D"]
    assert "contradict each other at step B" in s.finding


# Scenario 5 / test 9 - physical only stays UNCERTAIN (behaviour unchanged)
def test_scenario5_physical_only_uncertain(coordinator, walk):
    result, s = run(coordinator, walk, "ABCD")
    assert result.overall_status == JourneyStatus.UNCERTAIN
    assert result.violations == []
    assert s.finding == "Awaiting digital-channel confirmation."
    assert s.digital_trace == []


# 14. UNCERTAIN -> COMPLETED when matching digital evidence arrives (no special-casing: same engine re-run)
def test_transition_uncertain_to_completed(coordinator, walk):
    coordinator.add_physical_events(walk("ABCD"))
    assert coordinator.result().overall_status == JourneyStatus.UNCERTAIN
    coordinator.inject_digital_preset(FULL_TRACE)
    assert coordinator.result().overall_status == JourneyStatus.COMPLETED


# 15. OMISSION -> PHANTOM_COMPLETION when digital B completion arrives
def test_transition_omission_to_phantom(coordinator, walk):
    coordinator.add_physical_events(walk("ACD"))
    first = coordinator.result()
    assert first.violations[0].type == ViolationType.OMISSION and first.violations[0].step_id == "B"
    coordinator.inject_digital_preset(FULL_TRACE)
    second = coordinator.result()
    assert second.violations[0].type == ViolationType.PHANTOM_COMPLETION and second.violations[0].step_id == "B"


def test_omission_remains_when_digital_also_lacks_b(coordinator, walk):
    coordinator.add_physical_events(walk("ACD"))
    coordinator.inject_digital_preset(WITHOUT_B)
    assert coordinator.result().violations[0].type == ViolationType.OMISSION


def test_contradiction_arrives_after_physical_b(coordinator, walk):
    coordinator.add_physical_events(walk("AB"))
    coordinator.inject_digital_preset(B_FAILED)
    assert coordinator.result().violations[0].type == ViolationType.CHANNEL_CONTRADICTION


def test_clear_digital_reverts_verdict(coordinator, walk):
    coordinator.add_physical_events(walk("ABCD"))
    coordinator.inject_digital_preset(FULL_TRACE)
    assert coordinator.result().overall_status == JourneyStatus.COMPLETED
    coordinator.clear_digital()
    assert coordinator.result().overall_status == JourneyStatus.UNCERTAIN


def test_evidence_arriving_incrementally_each_step_via_coordinator(coordinator, walk):
    events = walk("ABCD")
    for e in events:
        coordinator.add_physical_events([e])
    assert coordinator.summary().physical_trace == ["A", "B", "C", "D"]
    assert coordinator.result().overall_status == JourneyStatus.UNCERTAIN


def test_result_matches_engine_called_directly(coordinator, walk):
    """The coordinator adds no logic to the verdict: it equals a direct M0 engine call on the same evidence."""
    from sentinel.conformance.engine import ConformanceEngine
    coordinator.add_physical_events(walk("ACD"))
    coordinator.inject_digital_preset(FULL_TRACE)
    ev = coordinator._get(None)
    direct = ConformanceEngine().evaluate(coordinator.procedure, ev.journey, ev.physical_events, ev.digital_events)
    got = coordinator.result()
    assert (got.overall_status, got.violations, got.step_states) == (direct.overall_status, direct.violations, direct.step_states)
