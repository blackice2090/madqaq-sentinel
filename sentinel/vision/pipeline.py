"""Perception pipeline: tracker output -> zones -> physical events -> M0 engine.

The M0 ConformanceEngine is used unchanged. Digital evidence is never invented:
`digital_events` is empty unless explicitly supplied by the caller.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sentinel.conformance.engine import ConformanceEngine
from sentinel.domain.models import (
    ConformanceResult, Journey, JourneyStatus, NormalizedEvent, ProcedureDefinition, ViolationType,
)
from sentinel.vision.event_emitter import PhysicalEventEmitter, TrackerDebug
from sentinel.vision.tracker import PersonTracker, TrackedPerson
from sentinel.vision.zones import Box, ZoneSet


@dataclass(frozen=True)
class PersonView:
    tracker_id: int
    confidence: float
    box: Box
    zone_id: str | None  # STABLE (dwell-confirmed) zone
    journey_id: str | None
    debug: TrackerDebug | None = None


@dataclass(frozen=True)
class FrameResult:
    persons: list[PersonView]
    new_events: list[NormalizedEvent]


@dataclass(frozen=True)
class JourneySummary:
    journey_id: str
    trace: list[str]
    current_zone: str | None
    event_count: int
    latest_event: NormalizedEvent | None
    m0_status: JourneyStatus
    headline: str
    reason: str
    violation_lines: list[str] = field(default_factory=list)


def physical_trace(events: list[NormalizedEvent]) -> list[str]:
    """Step sequence with consecutive duplicates collapsed, in time order."""
    trace: list[str] = []
    for e in sorted(events, key=lambda e: (e.timestamp, e.event_id)):
        if not trace or trace[-1] != e.step_id:
            trace.append(e.step_id)
    return trace


class PerceptionPipeline:
    def __init__(
        self,
        zones: ZoneSet,
        emitter: PhysicalEventEmitter,
        procedure: ProcedureDefinition,
        engine: ConformanceEngine | None = None,
        tracker: PersonTracker | None = None,
    ):
        steps = set(procedure.step_map())
        unknown = [z for z in zones.ids if z not in steps]
        if unknown:
            raise ValueError(f"zones {unknown} do not correspond to steps of procedure '{procedure.procedure_id}'")
        if emitter.procedure_id != procedure.procedure_id:
            raise ValueError("emitter procedure_id does not match procedure")
        self.zones, self.emitter, self.procedure = zones, emitter, procedure
        self.engine = engine or ConformanceEngine()
        self.tracker = tracker

    # ---- frame processing ------------------------------------------------
    def process_frame(self, frame: Any, now: datetime | None = None) -> FrameResult:
        if self.tracker is None:
            raise RuntimeError("no tracker configured; use process_persons() for camera-free operation")
        return self.process_persons(self.tracker.update(frame), now)

    def process_persons(self, persons: list[TrackedPerson], now: datetime | None = None) -> FrameResult:
        events = self.emitter.process(persons, now)
        views = []
        for p in persons:
            views.append(PersonView(p.tracker_id, p.confidence, p.box,
                                    self.emitter.zone_for_tracker(p.tracker_id),
                                    self.emitter.journey_for_tracker(p.tracker_id),
                                    self.emitter.debug_for_tracker(p.tracker_id)))
        return FrameResult(views, events)

    def reset(self) -> None:
        self.emitter.reset()
        if self.tracker is not None:
            self.tracker.reset()

    # ---- conformance -----------------------------------------------------
    def evaluate(self, journey_id: str, digital_events: list[NormalizedEvent] | None = None) -> ConformanceResult:
        rec = self.emitter.journeys[journey_id]
        journey = Journey(journey_id=journey_id, procedure_id=self.procedure.procedure_id, started_at=rec.started_at)
        return self.engine.evaluate(self.procedure, journey, list(rec.events), list(digital_events or []))

    def focus_journey_id(self) -> str | None:
        """Most recently started journey (what the demo panel shows)."""
        journeys = self.emitter.journeys
        if not journeys:
            return None
        return max(journeys.values(), key=lambda j: j.started_at).journey_id

    def summarize(self, journey_id: str, digital_events: list[NormalizedEvent] | None = None) -> JourneySummary:
        rec = self.emitter.journeys[journey_id]
        result = self.evaluate(journey_id, digital_events)
        trace = physical_trace(rec.events)
        required = [s.step_id for s in self.procedure.ordered_steps() if s.required]
        violation_lines = [
            f"Missing step: {v.step_id}" if v.type == ViolationType.OMISSION else v.message
            for v in result.violations
        ]
        if result.violations:
            kinds = ", ".join(dict.fromkeys(v.type.value for v in result.violations))
            headline, reason = "VIOLATED", kinds
        elif result.overall_status == JourneyStatus.COMPLETED:
            headline, reason = "CONFORMANT", "physical and digital evidence agree"
        elif all(s in trace for s in required):
            headline, reason = "PHYSICAL TRACE COMPLETE", "awaiting digital-channel confirmation"
        else:
            headline, reason = "PHYSICAL TRACE IN PROGRESS", "single-channel evidence; digital channel not connected"
        return JourneySummary(
            journey_id=journey_id, trace=trace, current_zone=rec.current_zone,
            event_count=len(rec.events), latest_event=rec.events[-1] if rec.events else None,
            m0_status=result.overall_status, headline=headline, reason=reason, violation_lines=violation_lines,
        )
