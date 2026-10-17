"""Judge-friendly wording. PRESENTATION ONLY: maps engine outputs to text; never alters them."""
from __future__ import annotations

from sentinel.domain.models import EventType, JourneyStatus, ProcedureDefinition, StepState, Violation, ViolationType

SIM_LABEL = "SIMULATED DIGITAL CHANNEL"
SIM_FOOTER = "Digital channel is simulated for demonstration."
PRIVACY_FOOTER = "Temporary tracking only • No face recognition • No persistent identity"
SIM_DISCLAIMER_LONG = (
    "The digital channel is a local simulator used to demonstrate cross-channel conformance logic. "
    "It is not an integration with a production checkpoint system. Field accuracy is not established."
)
CONTROLS_TEXT = ("1 Digital full trace   2 Digital without B   3 Digital B failed   "
                 "0 Clear digital   S Save evidence   R Reset   Q Quit")

COMPLETED_TEXT = "Physical and digital evidence agree."
UNCERTAIN_TEXT = "Awaiting sufficient cross-channel evidence."
NO_JOURNEY_TEXT = "Enter Zone A to begin a journey."


def humanize(name: str) -> str:
    """'CREDENTIAL_CHECK' -> 'Credential Check'. Already-friendly names are left alone."""
    text = " ".join(name.replace("_", " ").split())
    return text.title() if text.isupper() else text


def step_names(procedure: ProcedureDefinition) -> dict[str, str]:
    return {s.step_id: humanize(s.name) for s in procedure.ordered_steps()}


def step_label(step_id: str, names: dict[str, str]) -> str:
    return f"{step_id} — {names[step_id]}" if step_id in names else step_id


def violation_label(vt: ViolationType) -> str:
    return vt.value.replace("_", " ")


def verdict_headline(status: JourneyStatus | None) -> str:
    """Large verdict word. None means there is no journey yet."""
    if status is None:
        return "WAITING"
    return {JourneyStatus.COMPLETED: "COMPLETED", JourneyStatus.VIOLATED: "VIOLATED",
            JourneyStatus.UNCERTAIN: "UNCERTAIN", JourneyStatus.ACTIVE: "IN PROGRESS"}[status]


def human_finding(v: Violation, names: dict[str, str]) -> str:
    name = names.get(v.step_id, v.step_id)
    if v.type == ViolationType.OMISSION:
        return f"Required step {v.step_id} — {name} was skipped."
    if v.type == ViolationType.PHANTOM_COMPLETION:
        return f"{name} was recorded digitally, but no supporting physical evidence was observed."
    if v.type == ViolationType.CHANNEL_CONTRADICTION:
        return f"Physical evidence and digital status disagree at {name}."
    if v.type == ViolationType.ORDER_INVERSION:
        base = "A required procedure step occurred out of sequence."
        if v.related_step_id and v.related_step_id in names:
            return f"{base} {name} was expected before {names[v.related_step_id]}."
        return base
    return v.message.replace("_", " ")


def primary_finding(status: JourneyStatus | None, violations: list[Violation], names: dict[str, str]) -> str:
    if status is None:
        return NO_JOURNEY_TEXT
    if violations:
        return human_finding(violations[0], names)
    if status == JourneyStatus.COMPLETED:
        return COMPLETED_TEXT
    return UNCERTAIN_TEXT


def step_state_view(state: StepState, violation_type: ViolationType | None = None) -> tuple[str, str]:
    """(indicator, short word) for a step row. Indicators: OK, MISSING, CONFLICT, UNCERTAIN, NOT REACHED."""
    if violation_type == ViolationType.OMISSION:
        return "MISSING", "Skipped"
    if violation_type == ViolationType.PHANTOM_COMPLETION:
        return "CONFLICT", "Digital only"
    if violation_type == ViolationType.CHANNEL_CONTRADICTION:
        return "CONFLICT", "Channels disagree"
    if violation_type == ViolationType.ORDER_INVERSION:
        return "CONFLICT", "Out of sequence"
    return {
        StepState.CONFIRMED: ("OK", "Confirmed"),
        StepState.INCOMPLETE: ("MISSING", "Missing"),
        StepState.CONTRADICTORY: ("CONFLICT", "Conflict"),
        StepState.UNCERTAIN: ("UNCERTAIN", "One channel only"),
        StepState.NOT_REACHED: ("NOT REACHED", "Not reached yet"),
    }[state]


def event_word(event_type: EventType) -> str:
    return {EventType.STEP_OBSERVED: "observed", EventType.STEP_COMPLETED: "completed",
            EventType.STEP_FAILED: "failed"}[event_type]
