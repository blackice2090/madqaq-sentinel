"""Dual-Channel Coordinator.

Owns the runtime evidence of each journey and re-evaluates the EXISTING M0
ConformanceEngine whenever either channel changes. It never creates, sorts or edits
evidence to steer a verdict: physical events come from M1, digital events from the
digital simulator (or any caller), and both are stored exactly as received, in
arrival order, in separate lists.
"""
from __future__ import annotations

from sentinel.conformance.engine import ConformanceEngine
from sentinel.digital.presets import PRESETS, PRESETS_BY_KEY, DigitalPreset
from sentinel.digital.simulator import DigitalEventSimulator
from sentinel.domain.models import (
    ConformanceResult, EventType, EvidenceSource, Journey, JourneyStatus, NormalizedEvent, ProcedureDefinition,
)
from sentinel.dual_channel.state import (
    DualChannelSummary, DuplicateInjectionError, EvidenceValidationError, JourneyEvidence,
    JourneyMismatchError, NoActiveJourneyError,
)

NO_JOURNEY_MESSAGE = "Enter Zone A to begin a journey before injecting digital evidence."


class DualChannelCoordinator:
    def __init__(
        self,
        procedure: ProcedureDefinition,
        engine: ConformanceEngine | None = None,
        simulator: DigitalEventSimulator | None = None,
    ):
        self.procedure = procedure
        self.engine = engine or ConformanceEngine()
        self.simulator = simulator or DigitalEventSimulator()
        self._journeys: dict[str, JourneyEvidence] = {}
        self._active: str | None = None

    # ---- state access ----------------------------------------------------
    @property
    def active_journey_id(self) -> str | None:
        return self._active

    @property
    def journey_ids(self) -> list[str]:
        return list(self._journeys)

    def physical_events(self, journey_id: str | None = None) -> list[NormalizedEvent]:
        return list(self._get(journey_id).physical_events)

    def digital_events(self, journey_id: str | None = None) -> list[NormalizedEvent]:
        return list(self._get(journey_id).digital_events)

    def result(self, journey_id: str | None = None) -> ConformanceResult:
        ev = self._get(journey_id)
        assert ev.result is not None
        return ev.result

    def _get(self, journey_id: str | None) -> JourneyEvidence:
        jid = journey_id or self._active
        if jid is None or jid not in self._journeys:
            raise NoActiveJourneyError(NO_JOURNEY_MESSAGE)
        return self._journeys[jid]

    # ---- evidence intake ---------------------------------------------------
    def add_physical_events(self, events: list[NormalizedEvent]) -> ConformanceResult | None:
        """Receive PHYSICAL events from M1. The first event of an unseen journey makes it the active journey."""
        if not events:
            return None
        for e in events:
            self._validate_common(e, EvidenceSource.PHYSICAL)
            if e.event_type != EventType.STEP_OBSERVED:
                raise EvidenceValidationError(f"Physical events must be STEP_OBSERVED, got {e.event_type.value}.")
        touched: list[str] = []
        for e in events:
            ev = self._journeys.get(e.journey_id)
            if ev is None:
                ev = JourneyEvidence(
                    journey=Journey(journey_id=e.journey_id, procedure_id=self.procedure.procedure_id, started_at=e.timestamp),
                    procedure=self.procedure,
                )
                self._journeys[e.journey_id] = ev
                self._active = e.journey_id
            if self._append_unique(ev.physical_events, e) and e.journey_id not in touched:
                touched.append(e.journey_id)
        for jid in touched:
            self._evaluate(jid)
        return self._journeys[events[-1].journey_id].result

    def add_digital_events(self, events: list[NormalizedEvent]) -> ConformanceResult | None:
        """Receive DIGITAL events. They may only bind to the ACTIVE live journey."""
        if not events:
            return None
        if self._active is None:
            raise NoActiveJourneyError(NO_JOURNEY_MESSAGE)
        for e in events:
            self._validate_common(e, EvidenceSource.DIGITAL)
            if e.event_type not in (EventType.STEP_COMPLETED, EventType.STEP_FAILED):
                raise EvidenceValidationError(
                    f"Digital events must be STEP_COMPLETED or STEP_FAILED, got {e.event_type.value}.")
            if e.journey_id != self._active:
                raise JourneyMismatchError(
                    "Digital event belongs to a different journey than the active live journey; evidence was not added.")
        ev = self._journeys[self._active]
        changed = False
        for e in events:
            changed |= self._append_unique(ev.digital_events, e)
        if changed:
            self._evaluate(self._active)
        return ev.result

    def _validate_common(self, e: NormalizedEvent, expected_source: EvidenceSource) -> None:
        if e.source != expected_source:
            raise EvidenceValidationError(
                f"A {e.source.value} event was offered to the {expected_source.value} channel; channels are kept separate.")
        if e.procedure_id != self.procedure.procedure_id:
            raise EvidenceValidationError(
                f"Event procedure '{e.procedure_id}' does not match the active procedure '{self.procedure.procedure_id}'.")
        if e.step_id not in self.procedure.step_map():
            raise EvidenceValidationError(f"Unknown step id '{e.step_id}' for procedure '{self.procedure.procedure_id}'.")

    @staticmethod
    def _append_unique(store: list[NormalizedEvent], e: NormalizedEvent) -> bool:
        for existing in store:
            if existing.event_id == e.event_id:
                if existing == e:
                    return False  # exact duplicate delivery: ignore
                raise EvidenceValidationError(f"Conflicting duplicate event_id {e.event_id}.")
        store.append(e)
        return True

    # ---- digital presets (demo) ---------------------------------------------
    def inject_digital_preset(self, preset: DigitalPreset | str) -> list[NormalizedEvent]:
        """Inject one simulated digital trace into the ACTIVE journey, once.

        Rejected cleanly with no active journey, an unknown preset, or when digital
        evidence is already present (clear it first). Never creates a journey.
        """
        if isinstance(preset, str):
            found = PRESETS.get(preset) or PRESETS_BY_KEY.get(preset)
            if found is None:
                raise EvidenceValidationError(f"Unknown digital preset '{preset}'.")
            preset = found
        if self._active is None:
            raise NoActiveJourneyError(NO_JOURNEY_MESSAGE)
        ev = self._journeys[self._active]
        if ev.injected_preset_id is not None or ev.digital_events:
            raise DuplicateInjectionError(
                "Digital evidence is already present for this journey. Press 0 to clear it first, or R to reset.")
        events = self.simulator.build_events(preset, self._active, self.procedure.procedure_id)
        self.add_digital_events(events)
        ev.injected_preset_id = preset.preset_id
        return events

    def clear_digital(self) -> ConformanceResult:
        """Remove digital evidence of the ACTIVE journey only; physical evidence is untouched."""
        ev = self._get(None)
        ev.digital_events.clear()
        ev.injected_preset_id = None
        self._evaluate(ev.journey.journey_id)
        return ev.result  # type: ignore[return-value]

    def reset(self) -> None:
        """Forget every journey and both channels."""
        self._journeys.clear()
        self._active = None

    # ---- evaluation / presentation -------------------------------------------
    def _evaluate(self, journey_id: str) -> None:
        ev = self._journeys[journey_id]
        ev.result = self.engine.evaluate(ev.procedure, ev.journey, list(ev.physical_events), list(ev.digital_events))

    def summary(self, journey_id: str | None = None) -> DualChannelSummary:
        ev = self._get(journey_id)
        result = ev.result
        assert result is not None
        if result.violations:
            finding = " ".join(v.message for v in result.violations)
        elif result.overall_status == JourneyStatus.COMPLETED:
            finding = "Dual-channel evidence agrees."
        elif result.overall_status == JourneyStatus.UNCERTAIN:
            if not ev.digital_events:
                finding = "Awaiting digital-channel confirmation."
            else:
                pending = [s.step_id for s in result.step_states if s.state.value in ("UNCERTAIN",)]
                finding = "Awaiting dual-channel confirmation for step(s): " + ", ".join(pending) + "." if pending \
                    else "Evidence is not yet conclusive."
        else:
            finding = "No evidence yet."
        return DualChannelSummary(
            journey_id=ev.journey.journey_id,
            expected=[s.step_id for s in self.procedure.ordered_steps()],
            physical_trace=_trace(ev.physical_events),
            digital_trace=_trace(ev.digital_events),
            physical_count=len(ev.physical_events),
            digital_count=len(ev.digital_events),
            status=result.overall_status,
            finding_codes=[v.type.value for v in result.violations],
            finding=finding,
            step_states=[(s.step_id, s.state) for s in result.step_states],
            started_at=ev.journey.started_at,
        )


def _trace(events: list[NormalizedEvent]) -> list[str]:
    """Display trace in ARRIVAL order (never re-ordered), consecutive repeats collapsed."""
    out: list[str] = []
    for e in events:
        label = e.step_id + ("(FAILED)" if e.event_type == EventType.STEP_FAILED else "")
        if not out or out[-1] != label:
            out.append(label)
    return out
