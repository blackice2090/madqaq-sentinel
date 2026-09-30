from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sentinel.domain.models import (
    EvidenceSource, EventType, Journey, NormalizedEvent, ProcedureDefinition, ProcedureStep,
)

BASE = datetime(2026, 9, 30, 6, 0, 0, tzinfo=timezone.utc)


def procedure() -> ProcedureDefinition:
    return ProcedureDefinition(
        procedure_id="generic-checkpoint-v1",
        name="Generic Four-Step Checkpoint",
        version=1,
        steps=[
            ProcedureStep(step_id="A", name="ENTRY", order=1),
            ProcedureStep(step_id="B", name="CREDENTIAL_CHECK", order=2),
            ProcedureStep(step_id="C", name="SCREENING", order=3),
            ProcedureStep(step_id="D", name="EXIT", order=4),
        ],
    )


def journey() -> Journey:
    return Journey(journey_id="J-M0-001", procedure_id="generic-checkpoint-v1", started_at=BASE)


def _events(seq: list[str], source: EvidenceSource, *, low_conf_step: str | None = None, failed_step: str | None = None):
    events = []
    for i, step in enumerate(seq):
        event_type = EventType.STEP_OBSERVED if source == EvidenceSource.PHYSICAL else EventType.STEP_COMPLETED
        if source == EvidenceSource.DIGITAL and failed_step == step:
            event_type = EventType.STEP_FAILED
        events.append(NormalizedEvent(
            event_id=f"{source.value[0]}-{i+1}-{step}",
            journey_id="J-M0-001",
            procedure_id="generic-checkpoint-v1",
            source=source,
            event_type=event_type,
            step_id=step,
            timestamp=BASE + timedelta(seconds=i * 10),
            confidence=0.30 if low_conf_step == step else 1.0,
        ))
    return events


def scenario(name: str):
    if name == "normal":
        p = _events(list("ABCD"), EvidenceSource.PHYSICAL)
        d = _events(list("ABCD"), EvidenceSource.DIGITAL)
        expected = "CONFORMANT"
    elif name == "omission_b":
        p = _events(list("ACD"), EvidenceSource.PHYSICAL)
        d = _events(list("ACD"), EvidenceSource.DIGITAL)
        expected = "OMISSION:B"
    elif name == "order_inversion_bc":
        p = _events(list("ACBD"), EvidenceSource.PHYSICAL)
        d = _events(list("ACBD"), EvidenceSource.DIGITAL)
        expected = "ORDER_INVERSION:B"
    elif name == "phantom_completion_b":
        p = _events(list("ACD"), EvidenceSource.PHYSICAL)
        d = _events(list("ABCD"), EvidenceSource.DIGITAL)
        expected = "PHANTOM_COMPLETION:B"
    elif name == "channel_contradiction_b":
        p = _events(list("ABCD"), EvidenceSource.PHYSICAL)
        d = _events(list("ABCD"), EvidenceSource.DIGITAL, failed_step="B")
        expected = "CHANNEL_CONTRADICTION:B"
    elif name == "uncertain_b":
        p = _events(list("AB"), EvidenceSource.PHYSICAL, low_conf_step="B")
        d = _events(list("A"), EvidenceSource.DIGITAL)
        expected = "UNCERTAIN"
    else:
        raise KeyError(name)
    return procedure(), journey(), p, d, expected


SCENARIOS = [
    "normal",
    "omission_b",
    "order_inversion_bc",
    "phantom_completion_b",
    "channel_contradiction_b",
    "uncertain_b",
]
