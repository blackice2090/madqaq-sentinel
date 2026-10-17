"""Benchmark case schema (M4.1).

A case is a self-contained, auditable record: the procedure, the raw physical and
digital event streams, the LATENT WORLD the generator built them from, and the ground
truth. No images, no identity, no personal data: only step ids, relative timestamps and
confidences.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from sentinel.domain.models import (
    EventType, EvidenceSource, Journey, NormalizedEvent, ProcedureDefinition, ProcedureStep, ViolationType,
)

BENCHMARK_VERSION = "mbench-1.0"
GENERATOR_VERSION = "mgen-1.0"
DEV_SEED = 20261017
FINAL_SEED = 20261123
EPOCH = datetime(2026, 1, 1, tzinfo=timezone.utc)


@dataclass(frozen=True)
class SplitSpec:
    name: str
    seed: int
    n_cases: int
    id_prefix: str


SPLITS: dict[str, SplitSpec] = {
    "dev": SplitSpec("dev", DEV_SEED, 300, "DEV"),
    "final": SplitSpec("final", FINAL_SEED, 1200, "FIN"),
}

VIOLATION_TYPES: tuple[str, ...] = tuple(v.value for v in ViolationType)
GT_STATUSES: tuple[str, ...] = ("COMPLETED", "VIOLATED", "UNCERTAIN")
PRED_STATUSES: tuple[str, ...] = ("COMPLETED", "VIOLATED", "UNCERTAIN", "ACTIVE")
STEP_IDS: tuple[str, ...] = ("A", "B", "C", "D")

# Sensor-confidence bands used by the generator. They are deliberately far from the
# engine's 0.50 threshold so no case sits on the boundary.
CONFIDENT_BAND = (80, 100)   # percent
WEAK_BAND = (10, 35)         # percent
CONFIDENCE_CUT = 0.50        # benchmark definition of "confident" observation

ViolationTypeName = Literal["OMISSION", "ORDER_INVERSION", "PHANTOM_COMPLETION", "CHANNEL_CONTRADICTION"]
SubsetName = Literal["core", "boundary", "robustness"]


def make_label(violation_type: str, step_id: str) -> str:
    return f"{violation_type}:{step_id}"


def parse_label(label: str) -> tuple[str, str]:
    violation_type, _, step_id = label.partition(":")
    return violation_type, step_id


class EventRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    source: Literal["PHYSICAL", "DIGITAL"]
    event_type: Literal["STEP_OBSERVED", "STEP_COMPLETED", "STEP_FAILED"]
    step_id: str
    t_ms: int
    confidence: float = Field(ge=0.0, le=1.0)


class DigitalRecord(BaseModel):
    """Latent: what the digital system recorded for a step."""
    model_config = ConfigDict(extra="forbid")

    step_id: str
    outcome: Literal["COMPLETED", "FAILED"]


class LatentWorld(BaseModel):
    """What really happened, before any sensing or logging noise."""
    model_config = ConfigDict(extra="forbid")

    performed: list[str]                       # steps physically performed, in true order
    weak_physical: list[str] = Field(default_factory=list)  # performed steps seen only at low confidence
    physical_online: bool = True               # False: no physical events exist (outage)
    digital_online: bool = True                # False: no digital events exist (outage)
    digital_record: list[DigitalRecord] = Field(default_factory=list)


class GroundTruthViolation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: ViolationTypeName
    step_id: str
    related_step_id: str | None = None

    @property
    def label(self) -> str:
        return make_label(self.type, self.step_id)


class StepSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str
    name: str
    required: bool = True
    order: int


class ProcedureSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    procedure_id: str
    name: str
    version: int = 1
    steps: list[StepSpec]


def reference_procedure_spec() -> ProcedureSpec:
    return ProcedureSpec(
        procedure_id="generic-checkpoint-v1",
        name="Generic Four-Step Checkpoint",
        steps=[
            StepSpec(step_id="A", name="ENTRY", order=1),
            StepSpec(step_id="B", name="CREDENTIAL_CHECK", order=2),
            StepSpec(step_id="C", name="SCREENING", order=3),
            StepSpec(step_id="D", name="EXIT", order=4),
        ],
    )


class BenchmarkCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    benchmark_version: str
    generator_version: str
    split: Literal["dev", "final"]
    seed: int
    index: int
    subset: SubsetName
    scenario_family: str
    noise_conditions: list[str] = Field(default_factory=list)
    procedure: ProcedureSpec
    world: LatentWorld
    physical_events: list[EventRecord]
    digital_events: list[EventRecord]
    ground_truth_status: Literal["COMPLETED", "VIOLATED", "UNCERTAIN"]
    ground_truth_violations: list[GroundTruthViolation]
    ground_truth_labels: list[str]

    @model_validator(mode="after")
    def _labels_match_violations(self) -> "BenchmarkCase":
        expected = sorted({v.label for v in self.ground_truth_violations})
        if self.ground_truth_labels != expected:
            raise ValueError("ground_truth_labels must equal the sorted set of violation labels")
        if self.ground_truth_status == "VIOLATED" and not expected:
            raise ValueError("VIOLATED cases need at least one ground-truth violation")
        if self.ground_truth_status != "VIOLATED" and expected:
            raise ValueError("only VIOLATED cases may carry ground-truth violations")
        return self


def case_to_json_line(case: BenchmarkCase) -> str:
    """Canonical, byte-stable serialization of one case."""
    return json.dumps(case.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def case_from_json_line(line: str) -> BenchmarkCase:
    return BenchmarkCase.model_validate(json.loads(line))


# ---- conversion to the project's domain objects --------------------------------------
def to_procedure(spec: ProcedureSpec) -> ProcedureDefinition:
    return ProcedureDefinition(
        procedure_id=spec.procedure_id, name=spec.name, version=spec.version,
        steps=[ProcedureStep(step_id=s.step_id, name=s.name, required=s.required, order=s.order) for s in spec.steps],
    )


def _to_event(case: BenchmarkCase, rec: EventRecord) -> NormalizedEvent:
    return NormalizedEvent(
        event_id=rec.event_id,
        journey_id=case.case_id,
        procedure_id=case.procedure.procedure_id,
        source=EvidenceSource(rec.source),
        event_type=EventType(rec.event_type),
        step_id=rec.step_id,
        timestamp=EPOCH + timedelta(milliseconds=rec.t_ms),
        confidence=rec.confidence,
    )


def case_to_domain(case: BenchmarkCase) -> tuple[ProcedureDefinition, Journey, list[NormalizedEvent], list[NormalizedEvent]]:
    procedure = to_procedure(case.procedure)
    journey = Journey(journey_id=case.case_id, procedure_id=procedure.procedure_id, started_at=EPOCH)
    physical = [_to_event(case, r) for r in case.physical_events]
    digital = [_to_event(case, r) for r in case.digital_events]
    return procedure, journey, physical, digital
