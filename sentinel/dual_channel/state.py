"""Per-journey evidence state and errors for the M2 dual-channel coordinator."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sentinel.domain.models import (
    ConformanceResult, Journey, JourneyStatus, NormalizedEvent, ProcedureDefinition, StepState,
)


class DualChannelError(Exception):
    """Base class. The message is always safe to show to the operator."""


class NoActiveJourneyError(DualChannelError):
    pass


class JourneyMismatchError(DualChannelError):
    pass


class EvidenceValidationError(DualChannelError):
    pass


class DuplicateInjectionError(DualChannelError):
    pass


@dataclass
class JourneyEvidence:
    """Everything the coordinator holds for one journey. The two channels stay in separate lists."""

    journey: Journey
    procedure: ProcedureDefinition
    physical_events: list[NormalizedEvent] = field(default_factory=list)
    digital_events: list[NormalizedEvent] = field(default_factory=list)
    result: ConformanceResult | None = None
    injected_preset_id: str | None = None  # digital preset currently present, if any


@dataclass(frozen=True)
class DualChannelSummary:
    journey_id: str
    expected: list[str]
    physical_trace: list[str]
    digital_trace: list[str]           # e.g. ["A", "B(FAILED)", "C"]
    physical_count: int
    digital_count: int
    status: JourneyStatus
    finding_codes: list[str]           # violation types from the engine, in engine order
    finding: str                       # human-readable explanation
    step_states: list[tuple[str, StepState]]
    digital_simulated: bool = True     # the digital channel is ALWAYS a simulator in M2
    started_at: datetime | None = None
