import pytest

from sentinel.domain.models import EventType, JourneyStatus, StepState, Violation, ViolationType
from sentinel.presentation import labels

NAMES = {"A": "Entry", "B": "Credential Check", "C": "Screening", "D": "Exit"}


# 2. verdict display mapping
@pytest.mark.parametrize("status, text", [
    (JourneyStatus.COMPLETED, "COMPLETED"), (JourneyStatus.VIOLATED, "VIOLATED"),
    (JourneyStatus.UNCERTAIN, "UNCERTAIN"), (JourneyStatus.ACTIVE, "IN PROGRESS"), (None, "WAITING"),
])
def test_verdict_headline(status, text):
    assert labels.verdict_headline(status) == text


def test_verdict_sentences():
    assert labels.primary_finding(JourneyStatus.COMPLETED, [], NAMES) == "Physical and digital evidence agree."
    assert labels.primary_finding(JourneyStatus.UNCERTAIN, [], NAMES) == "Awaiting sufficient cross-channel evidence."
    assert labels.primary_finding(None, [], NAMES) == "Enter Zone A to begin a journey."


# 3. human-readable violation labels and findings
@pytest.mark.parametrize("vt, text", [
    (ViolationType.OMISSION, "OMISSION"), (ViolationType.PHANTOM_COMPLETION, "PHANTOM COMPLETION"),
    (ViolationType.ORDER_INVERSION, "ORDER INVERSION"), (ViolationType.CHANNEL_CONTRADICTION, "CHANNEL CONTRADICTION"),
])
def test_violation_label(vt, text):
    assert labels.violation_label(vt) == text


def v(vt, step="B", related=None):
    return Violation(type=vt, step_id=step, message="engine says: RAW_ENUM_TEXT", related_step_id=related)


def test_human_findings_match_spec_wording():
    assert labels.human_finding(v(ViolationType.OMISSION), NAMES) == "Required step B — Credential Check was skipped."
    assert labels.human_finding(v(ViolationType.PHANTOM_COMPLETION), NAMES) == \
        "Credential Check was recorded digitally, but no supporting physical evidence was observed."
    assert labels.human_finding(v(ViolationType.CHANNEL_CONTRADICTION), NAMES) == \
        "Physical evidence and digital status disagree at Credential Check."
    inv = labels.human_finding(v(ViolationType.ORDER_INVERSION, "B", "C"), NAMES)
    assert inv.startswith("A required procedure step occurred out of sequence.")
    assert "Credential Check was expected before Screening" in inv


def test_presentation_does_not_change_engine_violation():
    original = v(ViolationType.PHANTOM_COMPLETION)
    labels.human_finding(original, NAMES)
    assert original.type == ViolationType.PHANTOM_COMPLETION and original.message == "engine says: RAW_ENUM_TEXT"


# 4. step-state presentation mapping
@pytest.mark.parametrize("state, vt, expected", [
    (StepState.CONFIRMED, None, ("OK", "Confirmed")),
    (StepState.UNCERTAIN, None, ("UNCERTAIN", "One channel only")),
    (StepState.NOT_REACHED, None, ("NOT REACHED", "Not reached yet")),
    (StepState.INCOMPLETE, None, ("MISSING", "Missing")),
    (StepState.CONTRADICTORY, None, ("CONFLICT", "Conflict")),
    (StepState.INCOMPLETE, ViolationType.OMISSION, ("MISSING", "Skipped")),
    (StepState.CONTRADICTORY, ViolationType.PHANTOM_COMPLETION, ("CONFLICT", "Digital only")),
    (StepState.CONTRADICTORY, ViolationType.CHANNEL_CONTRADICTION, ("CONFLICT", "Channels disagree")),
    (StepState.CONTRADICTORY, ViolationType.ORDER_INVERSION, ("CONFLICT", "Out of sequence")),
])
def test_step_state_view(state, vt, expected):
    assert labels.step_state_view(state, vt) == expected


def test_indicator_vocabulary_is_the_specified_one():
    seen = {labels.step_state_view(s, vt)[0] for s in StepState for vt in [None, *ViolationType]}
    assert seen == {"OK", "MISSING", "CONFLICT", "UNCERTAIN", "NOT REACHED"}


# 13. no raw underscores in any human-readable label
def test_labels_contain_no_raw_underscores():
    texts = []
    texts += [labels.violation_label(t) for t in ViolationType]
    texts += [labels.verdict_headline(s) for s in [*JourneyStatus, None]]
    texts += [w for s in StepState for vt in [None, *ViolationType] for w in labels.step_state_view(s, vt)]
    texts += [labels.event_word(e) for e in EventType]
    texts += [labels.human_finding(v(t, "B", "C"), NAMES) for t in ViolationType]
    texts += [labels.humanize("CREDENTIAL_CHECK"), labels.SIM_LABEL, labels.SIM_FOOTER, labels.PRIVACY_FOOTER,
              labels.CONTROLS_TEXT, labels.COMPLETED_TEXT, labels.UNCERTAIN_TEXT, labels.NO_JOURNEY_TEXT]
    assert all("_" not in t for t in texts), [t for t in texts if "_" in t]


def test_humanize():
    assert labels.humanize("CREDENTIAL_CHECK") == "Credential Check"
    assert labels.humanize("ENTRY") == "Entry"
    assert labels.humanize("Credential Check") == "Credential Check"


def test_disclosure_texts():
    assert labels.SIM_LABEL == "SIMULATED DIGITAL CHANNEL"
    assert labels.PRIVACY_FOOTER == "Temporary tracking only • No face recognition • No persistent identity"
    assert labels.SIM_FOOTER == "Digital channel is simulated for demonstration."
