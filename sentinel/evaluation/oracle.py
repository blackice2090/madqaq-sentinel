"""Benchmark oracle: ground truth derived from the LATENT WORLD (rules BDEF-1).

INDEPENDENCE: this module never imports, calls or mirrors the ConformanceEngine's code
path. It reasons about what really happened (the latent world the generator built) and
about what the digital system recorded, then applies the benchmark definitions below.

BDEF-1 (all steps of the reference procedure are required)
-----------------------------------------------------------
Let ``performed`` be the steps the subject really performed, in true order;
``weak`` those performed steps whose physical evidence is only low-confidence;
CP = performed minus weak (confidently observed), empty if the camera is offline;
``completed``/``failed`` the digital record (empty if the digital channel is offline);
order(s) the procedure order; maxCP = max order over CP;
maxEvidence = max order over CP and ``completed``.

* CHANNEL_CONTRADICTION:X  X in CP and the digital record says X FAILED.
* PHANTOM_COMPLETION:X     digital says X COMPLETED, X was NOT performed, order(X) < maxCP
                           (the subject confidently progressed beyond X).
* ORDER_INVERSION:X        X in CP and a higher-order CP step was performed before X.
                           related step = the highest-order such earlier step.
                           (X is "the step that was due earlier but happened late".)
* OMISSION:X               X not performed, no digital COMPLETED/FAILED record for X, and
                           order(X) < maxEvidence (a later step is evidenced).
* status: VIOLATED if any label; else COMPLETED if both channels are online and every
  step is in CP and COMPLETED; else UNCERTAIN (evidence cannot certify conformance).

Principle: no violation without positive evidence of a fault. A step that was performed
but only weakly observed is not a fault; it merely prevents certification.

AMBIGUITY (such candidates are rejected and regenerated, never silently labelled)
---------------------------------------------------------------------------------
* two ground-truth violations on the same step (a step cannot be unambiguously both);
* a FAILED digital record on a step that is not confidently observed;
* a weak physical step that is also out of order;
* a revisited (non-consecutive repeated) step;
* noise that changes the within-channel step order, ties timestamps, or otherwise makes
  the evidence stop matching the latent world.
"""
from __future__ import annotations

from sentinel.evaluation.schema import (
    CONFIDENCE_CUT, VIOLATION_TYPES, BenchmarkCase, GroundTruthViolation, LatentWorld, ProcedureSpec,
)


def _sorted_violations(violations: list[GroundTruthViolation]) -> list[GroundTruthViolation]:
    return sorted(violations, key=lambda v: (VIOLATION_TYPES.index(v.type), v.step_id))


def derive_ground_truth(world: LatentWorld, procedure: ProcedureSpec) -> tuple[str, list[GroundTruthViolation]]:
    steps = sorted(procedure.steps, key=lambda s: s.order)
    order = {s.step_id: s.order for s in steps}
    required = [s.step_id for s in steps if s.required]

    performed = list(world.performed)
    performed_set = set(performed)
    weak = set(world.weak_physical)
    cp_seq = [s for s in performed if s not in weak] if world.physical_online else []
    cp = set(cp_seq)
    records = world.digital_record if world.digital_online else []
    completed = {r.step_id for r in records if r.outcome == "COMPLETED"}
    failed = {r.step_id for r in records if r.outcome == "FAILED"}

    max_cp = max((order[s] for s in cp), default=0)
    max_evidence = max((order[s] for s in (cp | completed)), default=0)

    violations: list[GroundTruthViolation] = []
    for s in required:
        if s in cp and s in failed:
            violations.append(GroundTruthViolation(type="CHANNEL_CONTRADICTION", step_id=s))
    for s in required:
        if s in completed and s not in performed_set and order[s] < max_cp:
            violations.append(GroundTruthViolation(type="PHANTOM_COMPLETION", step_id=s))
    for idx, s in enumerate(cp_seq):
        higher_before = [e for e in cp_seq[:idx] if order[e] > order[s]]
        if higher_before:
            related = max(higher_before, key=lambda e: order[e])
            violations.append(GroundTruthViolation(type="ORDER_INVERSION", step_id=s, related_step_id=related))
    for s in required:
        if s not in performed_set and s not in completed and s not in failed and order[s] < max_evidence:
            violations.append(GroundTruthViolation(type="OMISSION", step_id=s))

    violations = _sorted_violations(violations)
    if violations:
        return "VIOLATED", violations
    all_dual = (
        world.physical_online and world.digital_online and not failed
        and all(s in cp and s in completed for s in required)
    )
    return ("COMPLETED" if all_dual else "UNCERTAIN"), []


# ---- audits ------------------------------------------------------------------------------
def _world_ambiguity(world: LatentWorld, violations: list[GroundTruthViolation],
                     procedure: ProcedureSpec) -> list[str]:
    reasons: list[str] = []
    order = {s.step_id: s.order for s in procedure.steps}
    steps = [v.step_id for v in violations]
    if len(steps) != len(set(steps)):
        reasons.append("same-step multi-fault: two ground-truth violations target one step")
    if len(world.performed) != len(set(world.performed)):
        reasons.append("revisited step: a step was performed more than once")
    weak = set(world.weak_physical)
    if not weak <= set(world.performed):
        reasons.append("weak physical step was never performed")
    cp = set(world.performed) - weak if world.physical_online else set()
    for r in world.digital_record:
        if r.outcome == "FAILED" and r.step_id not in cp:
            reasons.append(f"FAILED digital record on step {r.step_id}, which is not confidently observed")
    for idx, s in enumerate(world.performed):
        if s in weak and any(order[e] > order[s] for e in world.performed[:idx]):
            reasons.append("weak physical step is out of order")
    return reasons


def _dedup_events(events):
    seen: dict[str, object] = {}
    problems: list[str] = []
    for e in events:
        prior = seen.get(e.event_id)
        if prior is not None and prior != e:
            problems.append(f"conflicting duplicate event_id {e.event_id}")
        seen[e.event_id] = e
    return list(seen.values()), problems


def _collapse(seq: list) -> list:
    out: list = []
    for item in seq:
        if not out or out[-1] != item:
            out.append(item)
    return out


def _evidence_problems(case: BenchmarkCase) -> list[str]:
    """Does the (possibly noisy) event stream still realise the latent world?"""
    world = case.world
    problems: list[str] = []

    phys, dup_problems = _dedup_events(case.physical_events)
    problems += dup_problems
    if not world.physical_online:
        if case.physical_events:
            problems.append("physical channel offline but physical events exist")
    else:
        if len({e.t_ms for e in phys}) != len(phys):
            problems.append("physical timestamp tie")
        ordered = sorted(phys, key=lambda e: (e.t_ms, e.event_id))
        confident = [e for e in ordered if e.confidence >= CONFIDENCE_CUT]
        weak_obs = [e for e in ordered if e.confidence < CONFIDENCE_CUT]
        weak = set(world.weak_physical)
        if _collapse([e.step_id for e in confident]) != [s for s in world.performed if s not in weak]:
            problems.append("confident physical sequence does not match the performed steps")
        if any(e.event_type != "STEP_OBSERVED" or e.source != "PHYSICAL" for e in phys):
            problems.append("physical channel contains a non-physical event")
        for s in weak:
            if not any(e.step_id == s for e in weak_obs) or any(e.step_id == s for e in confident):
                problems.append(f"step {s} is not weakly-observed-only")
        if any(e.step_id not in set(world.performed) for e in weak_obs):
            problems.append("low-confidence observation of a step that was not performed")

    dig, dup_problems = _dedup_events(case.digital_events)
    problems += dup_problems
    if not world.digital_online:
        if case.digital_events:
            problems.append("digital channel offline but digital events exist")
    else:
        if len({e.t_ms for e in dig}) != len(dig):
            problems.append("digital timestamp tie")
        ordered = sorted(dig, key=lambda e: (e.t_ms, e.event_id))
        if any(e.event_type == "STEP_OBSERVED" or e.source != "DIGITAL" for e in dig):
            problems.append("digital channel contains a non-digital event")
        got = _collapse([(e.step_id, "COMPLETED" if e.event_type == "STEP_COMPLETED" else "FAILED") for e in ordered])
        want = _collapse([(r.step_id, r.outcome) for r in world.digital_record])
        if got != want:
            problems.append("digital record sequence does not match the latent digital record")
    return problems


def audit_case(case: BenchmarkCase) -> list[str]:
    """Independent audit. Returns problems; an empty list means the case is sound.

    1. stored ground truth equals the one re-derived from the latent world;
    2. the case is not ambiguous under the benchmark definitions;
    3. the event streams still realise the latent world.
    """
    problems: list[str] = []
    status, violations = derive_ground_truth(case.world, case.procedure)
    if status != case.ground_truth_status:
        problems.append(f"status mismatch: stored {case.ground_truth_status}, derived {status}")
    stored = [(v.type, v.step_id, v.related_step_id) for v in _sorted_violations(list(case.ground_truth_violations))]
    derived = [(v.type, v.step_id, v.related_step_id) for v in violations]
    if stored != derived:
        problems.append(f"violation mismatch: stored {stored}, derived {derived}")
    problems += _world_ambiguity(case.world, violations, case.procedure)
    problems += _evidence_problems(case)
    return problems
