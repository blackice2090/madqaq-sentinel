"""Evaluated systems (M4.1): the full engine and the internal ablations.

Channel isolation is enforced twice: the runner narrows the evidence it hands to a
system (``Evidence.restricted_to``), and every single-channel system REFUSES any event
from the other channel (``ChannelIsolationError``) instead of silently dropping it.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from sentinel.conformance.engine import ConformanceEngine
from sentinel.domain.models import EvidenceSource, Journey, NormalizedEvent, ProcedureDefinition


class ChannelIsolationError(ValueError):
    """A system was handed evidence from a channel it is not allowed to see."""


@dataclass(frozen=True)
class Evidence:
    procedure: ProcedureDefinition
    journey: Journey
    physical_events: tuple[NormalizedEvent, ...]
    digital_events: tuple[NormalizedEvent, ...]

    def restricted_to(self, channels: frozenset[EvidenceSource]) -> "Evidence":
        return Evidence(
            self.procedure, self.journey,
            self.physical_events if EvidenceSource.PHYSICAL in channels else (),
            self.digital_events if EvidenceSource.DIGITAL in channels else (),
        )


@dataclass(frozen=True)
class SystemOutput:
    status: str                  # COMPLETED | VIOLATED | UNCERTAIN | ACTIVE
    labels: frozenset[str]       # "TYPE:STEP"


class EvaluatedSystem(ABC):
    system_id: str
    display_name: str
    description: str
    channels: frozenset[EvidenceSource]

    def evaluate(self, evidence: Evidence) -> SystemOutput:
        if EvidenceSource.PHYSICAL not in self.channels and evidence.physical_events:
            raise ChannelIsolationError(f"{self.display_name} must not receive physical events.")
        if EvidenceSource.DIGITAL not in self.channels and evidence.digital_events:
            raise ChannelIsolationError(f"{self.display_name} must not receive digital events.")
        return self._run(evidence)

    @abstractmethod
    def _run(self, evidence: Evidence) -> SystemOutput: ...


def _from_result(result) -> SystemOutput:
    return SystemOutput(
        status=result.overall_status.value,
        labels=frozenset(f"{v.type.value}:{v.step_id}" for v in result.violations),
    )


BOTH = frozenset({EvidenceSource.PHYSICAL, EvidenceSource.DIGITAL})


class FullDualChannelSystem(EvaluatedSystem):
    system_id = "full_dual_channel"
    display_name = "MADQAQ full dual-channel"
    description = "The unmodified M0 ConformanceEngine given both physical and digital evidence."
    channels = BOTH

    def __init__(self, engine: ConformanceEngine | None = None):
        self.engine = engine or ConformanceEngine()

    def _run(self, evidence: Evidence) -> SystemOutput:
        return _from_result(self.engine.evaluate(
            evidence.procedure, evidence.journey, list(evidence.physical_events), list(evidence.digital_events)))


class PhysicalOnlyAblation(EvaluatedSystem):
    system_id = "physical_only_ablation"
    display_name = "Physical-only ablation"
    description = ("The same ConformanceEngine with the digital channel removed: it receives physical evidence only "
                   "(an internal ablation, not an external product).")
    channels = frozenset({EvidenceSource.PHYSICAL})

    def __init__(self, engine: ConformanceEngine | None = None):
        self.engine = engine or ConformanceEngine()

    def _run(self, evidence: Evidence) -> SystemOutput:
        return _from_result(self.engine.evaluate(
            evidence.procedure, evidence.journey, list(evidence.physical_events), []))


class DigitalOnlyAblation(EvaluatedSystem):
    system_id = "digital_only_ablation"
    display_name = "Digital-only ablation"
    description = ("The same ConformanceEngine with the physical channel removed: it receives digital evidence only "
                   "(an internal ablation, not an external product).")
    channels = frozenset({EvidenceSource.DIGITAL})

    def __init__(self, engine: ConformanceEngine | None = None):
        self.engine = engine or ConformanceEngine()

    def _run(self, evidence: Evidence) -> SystemOutput:
        return _from_result(self.engine.evaluate(
            evidence.procedure, evidence.journey, [], list(evidence.digital_events)))
