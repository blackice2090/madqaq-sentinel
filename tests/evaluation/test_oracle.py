"""The oracle: BDEF-1 on hand-built worlds, plus the ambiguity / consistency audit."""
import pytest

from sentinel.conformance.engine import ConformanceEngine
from sentinel.evaluation.oracle import audit_case, derive_ground_truth
from sentinel.evaluation.schema import DigitalRecord, LatentWorld, reference_procedure_spec
from tests.evaluation.conftest import cases_of

PROC = reference_procedure_spec()


def world(performed, digital, *, weak=(), physical_online=True, digital_online=True, failed=()):
    return LatentWorld(
        performed=list(performed), weak_physical=list(weak), physical_online=physical_online,
        digital_online=digital_online,
        digital_record=[DigitalRecord(step_id=s, outcome="FAILED" if s in failed else "COMPLETED") for s in digital])


def labels(w):
    status, violations = derive_ground_truth(w, PROC)
    return status, sorted(v.label for v in violations)


def test_clean_journey_is_completed():
    assert labels(world("ABCD", "ABCD")) == ("COMPLETED", [])


def test_omission_requires_absence_from_both_channels():
    assert labels(world("ACD", "ACD")) == ("VIOLATED", ["OMISSION:B"])
    assert labels(world("AD", "AD")) == ("VIOLATED", ["OMISSION:B", "OMISSION:C"])


def test_final_step_missing_is_not_an_omission_in_this_benchmark():
    # complete journeys only: nothing later is evidenced, so no omission is defined
    assert labels(world("ABC", "ABC"))[1] == []


def test_phantom_completion_needs_digital_claim_without_the_step_and_progress_beyond_it():
    assert labels(world("ACD", "ABCD")) == ("VIOLATED", ["PHANTOM_COMPLETION:B"])
    assert labels(world("ABC", "ABCD"))[1] == []        # D claimed but the subject has not progressed beyond D


def test_channel_contradiction_is_physical_presence_with_digital_failure():
    assert labels(world("ABCD", "ABCD", failed="B")) == ("VIOLATED", ["CHANNEL_CONTRADICTION:B"])


def test_order_inversion_labels_the_late_step_and_records_the_related_step():
    status, violations = derive_ground_truth(world("ACBD", "ACBD"), PROC)
    assert status == "VIOLATED" and [(v.label, v.related_step_id) for v in violations] == [("ORDER_INVERSION:B", "C")]
    assert labels(world("ACDB", "ACDB"))[1] == ["ORDER_INVERSION:B"]


def test_compound_faults_on_distinct_steps_are_all_labelled():
    assert labels(world("AD", "ABD"))[1] == ["OMISSION:C", "PHANTOM_COMPLETION:B"]
    assert labels(world("ACD", "ABCD", failed="C"))[1] == ["CHANNEL_CONTRADICTION:C", "PHANTOM_COMPLETION:B"]
    assert labels(world("ADC", "ABDC"))[1] == ["ORDER_INVERSION:C", "PHANTOM_COMPLETION:B"]


def test_single_channel_availability_is_uncertain_not_a_violation():
    assert labels(world("ABCD", "", digital_online=False)) == ("UNCERTAIN", [])
    assert labels(world("ABCD", "ABCD", physical_online=False)) == ("UNCERTAIN", [])


def test_weak_observation_of_a_performed_step_is_uncertain_not_a_fault():
    assert labels(world("ABCD", "ABCD", weak="B")) == ("UNCERTAIN", [])
    assert labels(world("ABCD", "ABCD", weak="D")) == ("UNCERTAIN", [])


def test_derivation_never_needs_the_engine(monkeypatch):
    monkeypatch.setattr(ConformanceEngine, "evaluate", lambda *a, **k: (_ for _ in ()).throw(AssertionError))
    assert labels(world("ACD", "ABCD"))[1] == ["PHANTOM_COMPLETION:B"]


# ---- audit -----------------------------------------------------------------------------
def _sample(dev_split, family):
    return [c for c in cases_of(dev_split, family) if not c.noise_conditions][0]


def test_audit_accepts_generated_cases(dev_split):
    assert audit_case(_sample(dev_split, "phantom_single")) == []


def test_audit_detects_tampered_ground_truth(dev_split):
    c = _sample(dev_split, "conformant_clean")
    bad = c.model_copy(update={"ground_truth_status": "UNCERTAIN"})
    assert any("status mismatch" in p for p in audit_case(bad))


def test_audit_flags_same_step_multi_fault():
    # B is both physically inverted and digitally FAILED: two faults on one step
    problems = [p for p in audit_case_world_only(world("ACBD", "ACBD", failed="B"))]
    assert any("same-step multi-fault" in p for p in problems)


def test_audit_flags_failed_record_on_unobserved_step():
    problems = audit_case_world_only(world("ACD", "ABCD", failed="B"))
    assert any("not confidently observed" in p for p in problems)


def test_audit_flags_revisits_and_weak_out_of_order():
    assert any("revisited" in p for p in audit_case_world_only(world("ABCB", "ABCD")))
    assert any("weak physical step is out of order" in p for p in audit_case_world_only(world("ACBD", "ACBD", weak="B")))


def audit_case_world_only(w):
    from sentinel.evaluation.oracle import _world_ambiguity
    status, violations = derive_ground_truth(w, PROC)
    return _world_ambiguity(w, violations, PROC)


def test_audit_detects_noise_that_reorders_events(dev_split):
    c = _sample(dev_split, "inversion_single")
    phys = [e.model_copy() for e in c.physical_events]
    phys[1].t_ms, phys[2].t_ms = phys[2].t_ms, phys[1].t_ms          # swap two steps in time
    bad = c.model_copy(update={"physical_events": phys})
    assert any("does not match the performed steps" in p for p in audit_case(bad))


def test_audit_detects_timestamp_ties_and_conflicting_duplicates(dev_split):
    c = _sample(dev_split, "conformant_clean")
    phys = [e.model_copy() for e in c.physical_events]
    phys[1].t_ms = phys[0].t_ms
    assert any("timestamp tie" in p for p in audit_case(c.model_copy(update={"physical_events": phys})))
    dup = c.physical_events[0].model_copy(update={"confidence": 0.5})
    assert any("conflicting duplicate" in p for p in audit_case(
        c.model_copy(update={"physical_events": c.physical_events + [dup]})))


def test_audit_detects_events_on_an_offline_channel(dev_split):
    c = _sample(dev_split, "uncertain_physical_only")
    assert audit_case(c) == []
    bad = c.model_copy(update={"digital_events": _sample(dev_split, "conformant_clean").digital_events})
    assert any("digital channel offline" in p for p in audit_case(bad))
