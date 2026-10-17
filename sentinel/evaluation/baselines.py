"""Simple procedure-check baseline (M4.1): transparent, deliberately NOT cross-channel.

Exact rules
-----------
1. Evidence that a step "appears": a physical STEP_OBSERVED with confidence >= 0.50, or
   a digital STEP_COMPLETED. STEP_FAILED never counts as the step appearing.
2. OMISSION:X   for every required step X that appears in NEITHER channel.
3. ORDER_INVERSION:X  for every step X that occurs after a higher-order step within one
   channel's time-ordered, consecutive-duplicate-collapsed sequence (each channel is
   checked on its own; channels are never merged or compared with each other).
4. status: VIOLATED if any label was raised, otherwise COMPLETED. There is no UNCERTAIN.

What it does NOT do (by design): no cross-channel contradiction, no unsupported-digital-
completion (phantom) reasoning, no per-channel confirmation. It is a reasonable simple
checker, not a sabotaged one: it tolerates duplicates, ignores below-threshold physical
observations, and is insensitive to clock offsets between channels.
"""
from __future__ import annotations

from sentinel.domain.models import EventType
from sentinel.evaluation.adapters import BOTH, EvaluatedSystem, Evidence, SystemOutput

CONFIDENCE_THRESHOLD = 0.50

RULES: tuple[str, ...] = (
    "A step appears if a physical STEP_OBSERVED (confidence >= 0.50) or a digital STEP_COMPLETED names it; STEP_FAILED never counts.",
    "OMISSION:X is raised for every required step X that appears in neither channel.",
    "ORDER_INVERSION:X is raised for every step X that occurs after a higher-order step within one channel's collapsed time-ordered sequence; channels are never merged.",
    "Status is VIOLATED if any label was raised, otherwise COMPLETED; there is no UNCERTAIN.",
    "No cross-channel contradiction and no unsupported-digital-completion (phantom) reasoning.",
)


def _collapsed_steps(events) -> list[str]:
    out: list[str] = []
    for e in sorted(events, key=lambda e: (e.timestamp, e.event_id)):
        if not out or out[-1] != e.step_id:
            out.append(e.step_id)
    return out


class SimpleProcedureCheck(EvaluatedSystem):
    system_id = "simple_procedure_check"
    display_name = "Simple procedure-check baseline"
    description = "Transparent required-steps-present + monotonic-order checker; no cross-channel reasoning."
    channels = BOTH

    def _run(self, evidence: Evidence) -> SystemOutput:
        steps = evidence.procedure.ordered_steps()
        order = {s.step_id: s.order for s in steps}
        required = [s.step_id for s in steps if s.required]

        physical = [e for e in evidence.physical_events
                    if e.event_type == EventType.STEP_OBSERVED and e.confidence >= CONFIDENCE_THRESHOLD]
        digital = [e for e in evidence.digital_events if e.event_type == EventType.STEP_COMPLETED]

        appears = {e.step_id for e in physical} | {e.step_id for e in digital}
        labels = {f"OMISSION:{s}" for s in required if s not in appears}
        for sequence in (_collapsed_steps(physical), _collapsed_steps(digital)):
            highest = 0
            for step in sequence:
                if order[step] < highest:
                    labels.add(f"ORDER_INVERSION:{step}")
                else:
                    highest = order[step]
        return SystemOutput(status="VIOLATED" if labels else "COMPLETED", labels=frozenset(labels))


def default_systems() -> list[EvaluatedSystem]:
    from sentinel.evaluation.adapters import DigitalOnlyAblation, FullDualChannelSystem, PhysicalOnlyAblation
    return [FullDualChannelSystem(), PhysicalOnlyAblation(), DigitalOnlyAblation(), SimpleProcedureCheck()]
