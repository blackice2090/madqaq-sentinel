from sentinel.digital import B_FAILED, FULL_TRACE, WITHOUT_B
from sentinel.presentation import build_dashboard_model
from sentinel.vision.event_emitter import TrackerDebug
from sentinel.vision.pipeline import PersonView


def model(coordinator, walk, physical=None, preset=None, **kw):
    if physical:
        coordinator.add_physical_events(walk(physical))
    if preset:
        coordinator.inject_digital_preset(preset)
    return build_dashboard_model(coordinator, **kw)


def steps(m):
    return {s.step_id: (s.indicator, s.word) for s in m.steps}


def test_no_journey_state(coordinator):
    m = build_dashboard_model(coordinator)
    assert (m.has_journey, m.verdict, m.timeline, m.physical_trace, m.digital_trace) == (False, "WAITING", [], [], [])
    assert all(s.indicator == "NOT REACHED" for s in m.steps)
    assert m.primary_finding == "Enter Zone A to begin a journey."
    assert [n for _, n in m.expected] == ["Entry", "Credential Check", "Screening", "Exit"]  # humanised, no underscores


def test_scenario_completed(coordinator, walk):
    m = model(coordinator, walk, "ABCD", FULL_TRACE)
    assert m.verdict == "COMPLETED" and m.violation_labels == []
    assert set(steps(m).values()) == {("OK", "Confirmed")}
    assert m.primary_finding == "Physical and digital evidence agree."


def test_scenario_phantom_completion(coordinator, walk):
    m = model(coordinator, walk, "ACD", FULL_TRACE)
    assert m.verdict == "VIOLATED" and m.violation_labels == ["PHANTOM COMPLETION"]
    assert steps(m)["B"] == ("CONFLICT", "Digital only")
    assert m.verdict_where == "B — Credential Check"
    assert m.primary_finding == "Credential Check was recorded digitally, but no supporting physical evidence was observed."


def test_scenario_omission(coordinator, walk):
    m = model(coordinator, walk, "ACD", WITHOUT_B)
    assert m.violation_labels == ["OMISSION"] and steps(m)["B"] == ("MISSING", "Skipped")
    assert m.primary_finding == "Required step B — Credential Check was skipped."


def test_scenario_channel_contradiction(coordinator, walk):
    m = model(coordinator, walk, "ABCD", B_FAILED)
    assert m.violation_labels == ["CHANNEL CONTRADICTION"] and steps(m)["B"] == ("CONFLICT", "Channels disagree")
    assert m.digital_trace == [("A", False), ("B", True), ("C", False), ("D", False)]
    assert m.primary_finding == "Physical evidence and digital status disagree at Credential Check."


def test_scenario_physical_only_uncertain(coordinator, walk):
    m = model(coordinator, walk, "ABCD")
    assert m.verdict == "UNCERTAIN" and m.primary_finding == "Awaiting sufficient cross-channel evidence."
    assert set(steps(m).values()) == {("UNCERTAIN", "One channel only")}
    assert m.digital_trace == [] and m.physical_trace == ["A", "B", "C", "D"]


def test_order_inversion_label(coordinator, walk):
    m = model(coordinator, walk, "ACB")
    assert m.violation_labels == ["ORDER INVERSION"]
    assert m.primary_finding.startswith("A required procedure step occurred out of sequence.")


# 10. reset clears the displayed timeline and everything else
def test_reset_clears_displayed_timeline(coordinator, walk):
    m = model(coordinator, walk, "ABCD", FULL_TRACE)
    assert len(m.timeline) == 8
    coordinator.reset()
    after = build_dashboard_model(coordinator)
    assert after.timeline == [] and after.has_journey is False and after.physical_trace == [] and after.digital_trace == []


def test_clear_digital_removes_only_digital_rows(coordinator, walk):
    model(coordinator, walk, "ABCD", FULL_TRACE)
    coordinator.clear_digital()
    m = build_dashboard_model(coordinator)
    assert {e.channel for e in m.timeline} == {"PHYSICAL"} and m.digital_trace == []


# 11 / 12. debug diagnostics only with the debug flag
def person_with_debug(journey_id):
    dbg = TrackerDebug("B", "C", "B", 240.0, 600.0, (0.4, 0.9), (0.41, 0.95))
    return PersonView(7, 0.88, (0.3, 0.2, 0.5, 0.95), "B", journey_id, dbg)


def test_normal_mode_has_no_debug_lines(coordinator, walk):
    model(coordinator, walk, "AB")
    m = build_dashboard_model(coordinator, [person_with_debug(coordinator.active_journey_id)], debug=False)
    assert m.debug_lines == []
    assert "Tracking ID 7" in m.tracking_line and "Zone B — Credential Check" in m.tracking_line
    for word in ("Raw zone", "Candidate", "Dwell", "Stable", "Smoothed"):
        assert word not in m.tracking_line


def test_debug_mode_shows_diagnostics(coordinator, walk):
    model(coordinator, walk, "AB")
    m = build_dashboard_model(coordinator, [person_with_debug(coordinator.active_journey_id)], debug=True)
    text = "\n".join(m.debug_lines)
    assert "Raw zone: B" in text and "Candidate zone: C" in text and "Stable zone: B" in text
    assert "Dwell: 240 / 600 ms" in text and "Smoothed ground point: 0.410, 0.950" in text


def test_debug_mode_without_person(coordinator):
    assert build_dashboard_model(coordinator, [], debug=True).debug_lines == ["Debug: no person tracked"]
    assert build_dashboard_model(coordinator, [], debug=False).debug_lines == []
