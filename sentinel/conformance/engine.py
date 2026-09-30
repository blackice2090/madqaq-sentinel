from __future__ import annotations

from sentinel.domain.models import (
    ConformanceResult,
    EvidenceSource,
    EventType,
    Journey,
    JourneyStatus,
    NormalizedEvent,
    ProcedureDefinition,
    StepAssessment,
    StepState,
    Violation,
    ViolationType,
)


class ConformanceEngine:
    """Deterministic M0 procedure-conformance engine.

    M0 deliberately handles a linear procedure graph. It compares independent
    physical and digital evidence and returns semantic, step-specific outcomes.
    """

    def __init__(self, physical_confidence_threshold: float = 0.50, engine_version: str = "m0.1"):
        if not 0.0 <= physical_confidence_threshold <= 1.0:
            raise ValueError("physical_confidence_threshold must be within [0, 1]")
        self.threshold = physical_confidence_threshold
        self.engine_version = engine_version

    def evaluate(
        self,
        procedure: ProcedureDefinition,
        journey: Journey,
        physical_events: list[NormalizedEvent],
        digital_events: list[NormalizedEvent],
    ) -> ConformanceResult:
        self._validate_context(procedure, journey, physical_events + digital_events)

        ordered = procedure.ordered_steps()
        order = {step.step_id: step.order for step in ordered}
        required = [step.step_id for step in ordered if step.required]

        physical_all = self._ordered_events(physical_events, EvidenceSource.PHYSICAL)
        digital_all = self._ordered_events(digital_events, EvidenceSource.DIGITAL)

        physical_confident = [
            e for e in physical_all
            if e.event_type == EventType.STEP_OBSERVED and e.confidence >= self.threshold
        ]
        physical_low = [
            e for e in physical_all
            if e.event_type == EventType.STEP_OBSERVED and e.confidence < self.threshold
        ]
        digital_completed = [e for e in digital_all if e.event_type == EventType.STEP_COMPLETED]
        digital_failed = [e for e in digital_all if e.event_type == EventType.STEP_FAILED]

        p_seq = self._dedup_sequence(physical_confident)
        d_seq = self._dedup_sequence(digital_completed)
        p_set = set(p_seq)
        d_set = set(d_seq)
        p_low_set = {e.step_id for e in physical_low}
        d_failed_set = {e.step_id for e in digital_failed}

        violations: list[Violation] = []
        claimed_steps: set[str] = set()

        # 1) Explicit channel contradiction has highest precedence.
        for step_id in required:
            if step_id in p_set and step_id in d_failed_set:
                violations.append(Violation(
                    type=ViolationType.CHANNEL_CONTRADICTION,
                    step_id=step_id,
                    message=f"Physical evidence and digital status contradict each other at step {step_id}.",
                ))
                claimed_steps.add(step_id)

        # 2) Phantom completion: digital completion unsupported by physical evidence
        # after the physical journey has advanced beyond the step.
        max_physical_order = max((order[s] for s in p_set), default=0)
        for step_id in required:
            if step_id in claimed_steps:
                continue
            if step_id in d_set and step_id not in p_set and max_physical_order > order[step_id]:
                violations.append(Violation(
                    type=ViolationType.PHANTOM_COMPLETION,
                    step_id=step_id,
                    message=f"Digital completion for step {step_id} has no supporting physical evidence.",
                ))
                claimed_steps.add(step_id)

        # 3) Order inversion. Prefer physical trace; digital is checked if physical is monotonic.
        inversion = self._first_inversion(p_seq, order) or self._first_inversion(d_seq, order)
        if inversion:
            earlier_expected, observed_before = inversion
            step_id = earlier_expected
            if step_id not in claimed_steps:
                violations.append(Violation(
                    type=ViolationType.ORDER_INVERSION,
                    step_id=step_id,
                    related_step_id=observed_before,
                    message=f"Step {observed_before} occurred before required step {step_id}.",
                ))
                claimed_steps.add(step_id)

        # 4) Omission: a required step is absent from both channels while a later
        # required step is confidently observed/recorded.
        union_seen = p_set | d_set
        max_seen_order = max((order[s] for s in union_seen), default=0)
        for idx, step_id in enumerate(required):
            if step_id in claimed_steps:
                continue
            if step_id not in union_seen and max_seen_order > order[step_id]:
                prev_step = required[idx - 1] if idx > 0 else None
                next_step = next((s for s in required[idx + 1:] if s in union_seen), None)
                if prev_step and next_step:
                    msg = f"Required step {step_id} is missing between {prev_step} and {next_step}."
                elif next_step:
                    msg = f"Required step {step_id} is missing before {next_step}."
                else:
                    msg = f"Required step {step_id} is missing."
                violations.append(Violation(
                    type=ViolationType.OMISSION,
                    step_id=step_id,
                    message=msg,
                ))
                claimed_steps.add(step_id)

        # Step states + uncertainty. Low-confidence evidence does not override a
        # specific supported violation.
        step_states: list[StepAssessment] = []
        has_uncertain = False
        for step_id in [s.step_id for s in ordered]:
            v = next((v for v in violations if v.step_id == step_id), None)
            if v is not None:
                state = StepState.CONTRADICTORY if v.type in {
                    ViolationType.PHANTOM_COMPLETION,
                    ViolationType.CHANNEL_CONTRADICTION,
                    ViolationType.ORDER_INVERSION,
                } else StepState.INCOMPLETE
            elif step_id in p_set and step_id in d_set:
                state = StepState.CONFIRMED
            elif step_id in p_low_set and step_id not in d_set:
                state = StepState.UNCERTAIN
                has_uncertain = True
            elif step_id in union_seen:
                # Single-channel evidence can support progress in M0, but is not
                # labeled CONFIRMED across both channels.
                state = StepState.UNCERTAIN
                has_uncertain = True
            else:
                state = StepState.NOT_REACHED
            step_states.append(StepAssessment(step_id=step_id, state=state))

        if violations:
            overall = JourneyStatus.VIOLATED
        elif has_uncertain:
            overall = JourneyStatus.UNCERTAIN
        elif all(s.state == StepState.CONFIRMED for s in step_states if procedure.step_map()[s.step_id].required):
            overall = JourneyStatus.COMPLETED
        else:
            overall = JourneyStatus.ACTIVE

        return ConformanceResult(
            journey_id=journey.journey_id,
            procedure_id=procedure.procedure_id,
            overall_status=overall,
            step_states=step_states,
            violations=violations,
            engine_version=self.engine_version,
        )

    @staticmethod
    def _ordered_events(events: list[NormalizedEvent], source: EvidenceSource) -> list[NormalizedEvent]:
        filtered = [e for e in events if e.source == source]
        return sorted(filtered, key=lambda e: (e.timestamp, e.event_id))

    @staticmethod
    def _dedup_sequence(events: list[NormalizedEvent]) -> list[str]:
        sequence: list[str] = []
        for event in events:
            if not sequence or sequence[-1] != event.step_id:
                sequence.append(event.step_id)
        return sequence

    @staticmethod
    def _first_inversion(sequence: list[str], order: dict[str, int]) -> tuple[str, str] | None:
        if len(sequence) < 2:
            return None
        max_step = sequence[0]
        max_order = order[max_step]
        for current in sequence[1:]:
            current_order = order[current]
            if current_order < max_order:
                # current should have happened before the previously observed max_step.
                return current, max_step
            if current_order > max_order:
                max_order = current_order
                max_step = current
        return None

    @staticmethod
    def _validate_context(
        procedure: ProcedureDefinition,
        journey: Journey,
        events: list[NormalizedEvent],
    ) -> None:
        if journey.procedure_id != procedure.procedure_id:
            raise ValueError("journey procedure_id does not match procedure")
        valid_steps = set(procedure.step_map())
        seen_ids: dict[str, NormalizedEvent] = {}
        for event in events:
            if event.journey_id != journey.journey_id:
                raise ValueError("event journey_id does not match journey")
            if event.procedure_id != procedure.procedure_id:
                raise ValueError("event procedure_id does not match procedure")
            if event.step_id not in valid_steps:
                raise ValueError(f"invalid step_id: {event.step_id}")
            existing = seen_ids.get(event.event_id)
            if existing is not None and existing != event:
                raise ValueError(f"conflicting duplicate event_id: {event.event_id}")
            seen_ids[event.event_id] = event
