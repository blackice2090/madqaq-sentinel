"""Everything the finalist dashboard shows, as plain data (no OpenCV / Pillow)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import tzinfo

from sentinel.domain.models import EventType
from sentinel.dual_channel import DualChannelCoordinator
from sentinel.presentation import labels
from sentinel.presentation.timeline import DEFAULT_LIMIT, TimelineEntry, build_timeline
from sentinel.vision.pipeline import PersonView


@dataclass(frozen=True)
class StepCard:
    step_id: str
    name: str
    indicator: str   # OK | MISSING | CONFLICT | UNCERTAIN | NOT REACHED
    word: str
    state: str       # engine StepState value (for evidence export)


@dataclass(frozen=True)
class DashboardModel:
    has_journey: bool
    journey_short: str | None
    expected: list[tuple[str, str]]
    physical_trace: list[str]
    digital_trace: list[tuple[str, bool]]   # (step_id, failed?)
    steps: list[StepCard]
    verdict: str
    violation_labels: list[str]
    verdict_where: str                      # e.g. "Step B — Credential Check"
    primary_finding: str
    extra_findings: int
    timeline: list[TimelineEntry]
    tracking_line: str
    debug_lines: list[str] = field(default_factory=list)
    sim_label: str = labels.SIM_LABEL

    @property
    def digital_event_count(self) -> int:
        return len(self.digital_trace)


def _debug_lines(person: PersonView | None) -> list[str]:
    d = person.debug if person else None
    if d is None:
        return ["Debug: no person tracked"]
    z = lambda v: v if v else "outside"  # noqa: E731
    return [
        f"Raw zone: {z(d.raw_zone)}",
        f"Candidate zone: {z(d.candidate_zone)}",
        f"Stable zone: {z(d.stable_zone)}",
        f"Dwell: {d.dwell_ms:.0f} / {d.dwell_target_ms:.0f} ms",
        f"Smoothed ground point: {d.smoothed_point[0]:.3f}, {d.smoothed_point[1]:.3f}",
    ]


def build_dashboard_model(
    coordinator: DualChannelCoordinator,
    persons: list[PersonView] | None = None,
    debug: bool = False,
    timeline_limit: int = DEFAULT_LIMIT,
    tz: tzinfo | None = None,
) -> DashboardModel:
    persons = persons or []
    proc = coordinator.procedure
    names = labels.step_names(proc)
    expected = [(s.step_id, names[s.step_id]) for s in proc.ordered_steps()]
    active = coordinator.active_journey_id

    focus = next((p for p in persons if active and p.journey_id == active), None) or (persons[0] if persons else None)
    if focus is None:
        tracking = "No person tracked"
    else:
        zone = f"Zone {labels.step_label(focus.zone_id, names)}" if focus.zone_id else "outside the zones"
        tracking = f"Tracking ID {focus.tracker_id} · {zone} · conf {focus.confidence:.2f}"
    debug_lines = _debug_lines(focus) if debug else []

    if not active:
        return DashboardModel(
            has_journey=False, journey_short=None, expected=expected, physical_trace=[], digital_trace=[],
            steps=[StepCard(sid, nm, "NOT REACHED", "Not reached yet", "NOT_REACHED") for sid, nm in expected],
            verdict=labels.verdict_headline(None), violation_labels=[], verdict_where="",
            primary_finding=labels.NO_JOURNEY_TEXT, extra_findings=0, timeline=[],
            tracking_line=tracking, debug_lines=debug_lines,
        )

    result = coordinator.result()
    summary = coordinator.summary()
    physical = coordinator.physical_events()
    digital = coordinator.digital_events()
    by_step_violation = {}
    for v in result.violations:
        by_step_violation.setdefault(v.step_id, v.type)
    steps = []
    for sa in result.step_states:
        indicator, word = labels.step_state_view(sa.state, by_step_violation.get(sa.step_id))
        steps.append(StepCard(sa.step_id, names[sa.step_id], indicator, word, sa.state.value))
    first = result.violations[0] if result.violations else None
    status = result.overall_status
    return DashboardModel(
        has_journey=True,
        journey_short=summary.journey_id[:8],
        expected=expected,
        physical_trace=[e.step_id for e in _collapse(physical)],
        digital_trace=[(e.step_id, e.event_type == EventType.STEP_FAILED) for e in _collapse(digital)],
        steps=steps,
        verdict=labels.verdict_headline(status),
        violation_labels=[labels.violation_label(v.type) for v in result.violations],
        verdict_where=labels.step_label(first.step_id, names) if first else "",
        primary_finding=labels.primary_finding(status, result.violations, names),
        extra_findings=max(0, len(result.violations) - 1),
        timeline=build_timeline(physical, digital, names, timeline_limit, tz),
        tracking_line=tracking,
        debug_lines=debug_lines,
    )


def _collapse(events):
    """Arrival-order events with consecutive repeats of the same step+type collapsed (display only)."""
    out = []
    for e in events:
        if not out or (out[-1].step_id, out[-1].event_type) != (e.step_id, e.event_type):
            out.append(e)
    return out
