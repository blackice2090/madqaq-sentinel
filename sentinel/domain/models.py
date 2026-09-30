from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EvidenceSource(str, Enum):
    PHYSICAL = "PHYSICAL"
    DIGITAL = "DIGITAL"


class EventType(str, Enum):
    STEP_OBSERVED = "STEP_OBSERVED"
    STEP_COMPLETED = "STEP_COMPLETED"
    STEP_FAILED = "STEP_FAILED"


class JourneyStatus(str, Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    VIOLATED = "VIOLATED"
    UNCERTAIN = "UNCERTAIN"


class StepState(str, Enum):
    CONFIRMED = "CONFIRMED"
    INCOMPLETE = "INCOMPLETE"
    CONTRADICTORY = "CONTRADICTORY"
    UNCERTAIN = "UNCERTAIN"
    NOT_REACHED = "NOT_REACHED"


class ViolationType(str, Enum):
    OMISSION = "OMISSION"
    ORDER_INVERSION = "ORDER_INVERSION"
    PHANTOM_COMPLETION = "PHANTOM_COMPLETION"
    CHANNEL_CONTRADICTION = "CHANNEL_CONTRADICTION"


class ProcedureStep(BaseModel):
    step_id: str
    name: str
    required: bool = True
    order: int = Field(ge=1)


class ProcedureDefinition(BaseModel):
    procedure_id: str
    name: str
    version: int = Field(ge=1, default=1)
    steps: list[ProcedureStep]

    @model_validator(mode="after")
    def validate_steps(self) -> "ProcedureDefinition":
        if not self.steps:
            raise ValueError("procedure must contain at least one step")
        ids = [s.step_id for s in self.steps]
        if len(ids) != len(set(ids)):
            raise ValueError("step_id values must be unique")
        orders = [s.order for s in self.steps]
        if len(orders) != len(set(orders)):
            raise ValueError("step order values must be unique")
        if sorted(orders) != list(range(1, len(self.steps) + 1)):
            raise ValueError("step order values must be contiguous starting at 1")
        return self

    def ordered_steps(self) -> list[ProcedureStep]:
        return sorted(self.steps, key=lambda s: s.order)

    def step_map(self) -> dict[str, ProcedureStep]:
        return {s.step_id: s for s in self.steps}


class Journey(BaseModel):
    journey_id: str
    procedure_id: str
    status: JourneyStatus = JourneyStatus.ACTIVE
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: datetime | None = None


class NormalizedEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    journey_id: str
    procedure_id: str
    source: EvidenceSource
    event_type: EventType
    step_id: str
    timestamp: datetime
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("timestamp")
    @classmethod
    def timestamp_must_be_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        return value


class StepAssessment(BaseModel):
    step_id: str
    state: StepState


class Violation(BaseModel):
    type: ViolationType
    step_id: str
    message: str
    severity: str = "HIGH"
    related_step_id: str | None = None


class ConformanceResult(BaseModel):
    journey_id: str
    procedure_id: str
    overall_status: JourneyStatus
    step_states: list[StepAssessment]
    violations: list[Violation]
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    engine_version: str = "m0.1"
