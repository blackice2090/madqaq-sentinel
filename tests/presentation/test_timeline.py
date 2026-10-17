from datetime import datetime, timedelta, timezone

from sentinel.digital import FULL_TRACE
from sentinel.presentation.timeline import build_timeline, format_time

NAMES = {"A": "Entry", "B": "Credential Check", "C": "Screening", "D": "Exit"}
UTC = timezone.utc


# 5. ordering
def test_timeline_is_chronological_across_channels(coordinator, walk):
    coordinator.add_physical_events(walk("ABCD"))
    coordinator.inject_digital_preset(FULL_TRACE)
    entries = build_timeline(coordinator.physical_events(), coordinator.digital_events(), NAMES, limit=100)
    stamps = [e.timestamp for e in entries]
    assert stamps == sorted(stamps)
    assert len(entries) == 8


def test_ties_put_physical_before_digital_then_arrival_order(coordinator, walk):
    phys = walk("A")
    t = phys[0].timestamp
    coordinator.add_physical_events(phys)
    coordinator.inject_digital_preset(FULL_TRACE)
    digital = [e.model_copy(update={"timestamp": t}) for e in coordinator.digital_events()]
    entries = build_timeline(phys, digital, NAMES, limit=100)
    assert [e.channel for e in entries] == ["PHYSICAL", "DIGITAL", "DIGITAL", "DIGITAL", "DIGITAL"]
    assert [e.step_id for e in entries[1:]] == ["A", "B", "C", "D"]


def test_latest_n_are_kept(coordinator, walk):
    coordinator.add_physical_events(walk("ABCD"))
    coordinator.inject_digital_preset(FULL_TRACE)
    full = build_timeline(coordinator.physical_events(), coordinator.digital_events(), NAMES, limit=100)
    last6 = build_timeline(coordinator.physical_events(), coordinator.digital_events(), NAMES, limit=6)
    assert [e.event_id for e in last6] == [e.event_id for e in full][-6:]
    assert build_timeline([], [], NAMES) == []


# 6. uses actual events only
def test_entries_map_one_to_one_to_real_events(coordinator, walk):
    coordinator.add_physical_events(walk("ACD"))
    coordinator.inject_digital_preset(FULL_TRACE)
    phys, dig = coordinator.physical_events(), coordinator.digital_events()
    entries = build_timeline(phys, dig, NAMES, limit=100)
    assert {e.event_id for e in entries} == {e.event_id for e in phys + dig}
    assert len(entries) == len(phys) + len(dig)  # nothing added, nothing dropped
    by_id = {e.event_id: e for e in phys + dig}
    for t in entries:
        src = by_id[t.event_id]
        assert (t.timestamp, t.step_id) == (src.timestamp, src.step_id)


def test_no_events_means_no_timeline_rows():
    assert build_timeline([], [], NAMES) == []


def test_entry_fields(coordinator, walk):
    coordinator.add_physical_events(walk("AB"))
    coordinator.inject_digital_preset("3")
    entries = build_timeline(coordinator.physical_events(), coordinator.digital_events(), NAMES, limit=100, tz=UTC)
    phys = [e for e in entries if e.channel == "PHYSICAL"]
    dig = [e for e in entries if e.channel == "DIGITAL"]
    assert all(e.confidence is not None and e.event_text == "observed" for e in phys)
    assert phys[0].detail.startswith("observed · conf 0.")
    assert all(e.confidence is None and e.simulated for e in dig)
    failed = [e for e in dig if e.step_id == "B"][0]
    assert failed.event_text == "failed" and failed.detail == "failed (simulated)"
    assert failed.step_name == "Credential Check"
    assert all(len(e.time_text) == 8 and e.time_text[2] == ":" for e in entries)


def test_format_time_uses_requested_timezone():
    ts = datetime(2026, 10, 17, 12, 41, 3, tzinfo=UTC)
    assert format_time(ts, UTC) == "12:41:03"
    assert format_time(ts, timezone(timedelta(hours=3))) == "15:41:03"
