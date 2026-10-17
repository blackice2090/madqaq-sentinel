"""Evaluated systems: channel isolation, the full-engine adapter, and the simple baseline's exact rules."""
from datetime import timedelta

import pytest

from sentinel.conformance.engine import ConformanceEngine
from sentinel.domain.models import EventType, EvidenceSource, Journey, NormalizedEvent
from sentinel.evaluation import baselines
from sentinel.evaluation.adapters import (
    ChannelIsolationError, DigitalOnlyAblation, Evidence, FullDualChannelSystem, PhysicalOnlyAblation,
)
from sentinel.evaluation.baselines import SimpleProcedureCheck, default_systems
from sentinel.evaluation.runner import build_evidence
from sentinel.evaluation.schema import EPOCH, reference_procedure_spec, to_procedure
from tests.evaluation.conftest import cases_of

PROC = to_procedure(reference_procedure_spec())
JOURNEY = Journey(journey_id="J", procedure_id=PROC.procedure_id, started_at=EPOCH)


def phys(step, t, conf=0.9, n=[0]):
    n[0] += 1
    return NormalizedEvent(event_id=f"P{n[0]}", journey_id="J", procedure_id=PROC.procedure_id,
                           source=EvidenceSource.PHYSICAL, event_type=EventType.STEP_OBSERVED, step_id=step,
                           timestamp=EPOCH + timedelta(seconds=t), confidence=conf)


def dig(step, t, failed=False, n=[0]):
    n[0] += 1
    return NormalizedEvent(event_id=f"D{n[0]}", journey_id="J", procedure_id=PROC.procedure_id,
                           source=EvidenceSource.DIGITAL,
                           event_type=EventType.STEP_FAILED if failed else EventType.STEP_COMPLETED, step_id=step,
                           timestamp=EPOCH + timedelta(seconds=t))


def evidence(p=(), d=()):
    return Evidence(PROC, JOURNEY, tuple(p), tuple(d))


class SpyEngine(ConformanceEngine):
    def __init__(self):
        super().__init__()
        self.calls = []

    def evaluate(self, procedure, journey, physical_events, digital_events):
        self.calls.append((list(physical_events), list(digital_events)))
        return super().evaluate(procedure, journey, physical_events, digital_events)


P_ACD = [phys("A", 0), phys("C", 10), phys("D", 20)]
D_ABCD = [dig("A", 1), dig("B", 11), dig("C", 21), dig("D", 31)]


# ---- channel isolation ---------------------------------------------------------------------
def test_physical_only_adapter_cannot_receive_digital_events():
    system = PhysicalOnlyAblation(SpyEngine())
    with pytest.raises(ChannelIsolationError):
        system.evaluate(evidence(P_ACD, D_ABCD))
    assert system.engine.calls == []                      # the engine never saw anything


def test_physical_only_adapter_hands_the_engine_no_digital_events():
    system = PhysicalOnlyAblation(SpyEngine())
    system.evaluate(evidence(P_ACD).restricted_to(system.channels))
    assert system.engine.calls == [(P_ACD, [])]
    full = evidence(P_ACD, D_ABCD).restricted_to(system.channels)
    assert full.digital_events == () and full.physical_events == tuple(P_ACD)


def test_digital_only_adapter_cannot_receive_physical_events():
    system = DigitalOnlyAblation(SpyEngine())
    with pytest.raises(ChannelIsolationError):
        system.evaluate(evidence(P_ACD, D_ABCD))
    system.evaluate(evidence((), D_ABCD))
    assert system.engine.calls == [([], D_ABCD)]


def test_full_system_uses_both_channels_and_the_unmodified_engine():
    system = FullDualChannelSystem(SpyEngine())
    out = system.evaluate(evidence(P_ACD, D_ABCD))
    assert system.engine.calls == [(P_ACD, D_ABCD)]
    assert out.labels == {"PHANTOM_COMPLETION:B"} and out.status == "VIOLATED"


def test_ablations_see_different_things_on_a_phantom_journey():
    ev = evidence(P_ACD, D_ABCD)
    assert PhysicalOnlyAblation().evaluate(ev.restricted_to(PhysicalOnlyAblation.channels)).labels == {"OMISSION:B"}
    assert DigitalOnlyAblation().evaluate(ev.restricted_to(DigitalOnlyAblation.channels)).labels == frozenset()


def test_system_ids_and_labels():
    systems = {s.system_id: s for s in default_systems()}
    assert list(systems) == ["full_dual_channel", "physical_only_ablation", "digital_only_ablation",
                             "simple_procedure_check"]
    assert "ablation" in systems["physical_only_ablation"].display_name.lower()
    assert "internal ablation" in systems["digital_only_ablation"].description


# ---- simple baseline ------------------------------------------------------------------------
simple = SimpleProcedureCheck()


def test_simple_baseline_has_no_phantom_logic():
    out = simple.evaluate(evidence(P_ACD, D_ABCD))          # a phantom journey
    assert out.labels == frozenset() and out.status == "COMPLETED"


def test_simple_baseline_has_no_contradiction_logic():
    p = [phys("A", 0), phys("B", 10), phys("C", 20), phys("D", 30)]
    d = [dig("A", 1), dig("B", 11, failed=True), dig("C", 21), dig("D", 31)]
    assert simple.evaluate(evidence(p, d)).labels == frozenset()


def test_simple_baseline_only_ever_emits_omission_and_inversion(dev_split):
    emitted = set()
    for case in dev_split.cases:
        emitted |= {l.split(":")[0] for l in simple.evaluate(build_evidence(case)).labels}
    assert emitted <= {"OMISSION", "ORDER_INVERSION"}


def test_simple_baseline_flags_missing_required_steps_in_either_channel():
    p = [phys("A", 0), phys("C", 10), phys("D", 20)]
    assert simple.evaluate(evidence(p, [])).labels == {"OMISSION:B"}
    assert simple.evaluate(evidence(p, [dig("B", 5)])).labels == frozenset()     # B appears digitally


def test_simple_baseline_flags_step_order_per_channel():
    p = [phys("A", 0), phys("C", 10), phys("B", 20), phys("D", 30)]
    assert simple.evaluate(evidence(p, [])).labels == {"ORDER_INVERSION:B"}


def test_simple_baseline_ignores_low_confidence_failed_records_and_duplicates():
    p = [phys("A", 0), phys("B", 10, conf=0.2), phys("C", 20), phys("C", 21), phys("D", 30)]
    assert simple.evaluate(evidence(p, [])).labels == {"OMISSION:B"}             # weak B does not count
    d = [dig("A", 0), dig("B", 5, failed=True), dig("C", 6), dig("D", 7)]
    assert simple.evaluate(evidence((), d)).labels == {"OMISSION:B"}             # FAILED is not an appearance


def test_simple_baseline_is_insensitive_to_clock_offset_between_channels():
    p = [phys("A", 0), phys("B", 10), phys("C", 20), phys("D", 30)]
    d = [dig("A", 100), dig("B", 110), dig("C", 120), dig("D", 130)]            # delayed digital events
    out = simple.evaluate(evidence(p, d))
    assert out.labels == frozenset() and out.status == "COMPLETED"


def test_simple_baseline_documents_its_rules():
    assert len(baselines.RULES) == 5 and any("no cross-channel" in r.lower() for r in baselines.RULES)
    assert "STEP_FAILED never counts" in baselines.RULES[0]


def test_full_system_matches_the_raw_engine_on_every_dev_case(dev_split):
    engine, full = ConformanceEngine(), FullDualChannelSystem()
    for case in cases_of(dev_split)[:60]:
        ev = build_evidence(case)
        raw = engine.evaluate(ev.procedure, ev.journey, list(ev.physical_events), list(ev.digital_events))
        out = full.evaluate(ev)
        assert out.status == raw.overall_status.value
        assert out.labels == {f"{v.type.value}:{v.step_id}" for v in raw.violations}
