import json
import re
from datetime import datetime, timedelta, timezone

import pytest

from sentinel.digital import B_FAILED, FULL_TRACE, WITHOUT_B
from sentinel.dual_channel import NoActiveJourneyError
from sentinel.presentation.evidence import build_evidence, save_snapshot, snapshot_basename, snapshot_slug

LOCAL = timezone(timedelta(hours=3))
NOW = datetime(2026, 10, 17, 17, 20, 15, tzinfo=LOCAL)


def fake_png(path):
    path.write_bytes(b"\x89PNG fake")
    return True


# 7. filename generation
def test_snapshot_basename_matches_spec_example():
    assert snapshot_basename(NOW, "PHANTOM_COMPLETION") == "2026-10-17_172015_PHANTOM_COMPLETION"


def test_snapshot_basename_sanitises_slug():
    assert snapshot_basename(NOW, "a/b c*") == "2026-10-17_172015_a_b_c"
    assert snapshot_basename(NOW, "") .endswith("_EVIDENCE")


@pytest.mark.parametrize("physical, preset, slug", [
    ("ACD", FULL_TRACE, "PHANTOM_COMPLETION"), ("ACD", WITHOUT_B, "OMISSION"),
    ("ABCD", B_FAILED, "CHANNEL_CONTRADICTION"), ("ABCD", FULL_TRACE, "COMPLETED"), ("ABCD", None, "UNCERTAIN"),
])
def test_slug_follows_verdict(coordinator, walk, physical, preset, slug):
    coordinator.add_physical_events(walk(physical))
    if preset:
        coordinator.inject_digital_preset(preset)
    assert snapshot_slug(coordinator) == slug


# 8 + 9. JSON evidence
def phantom(coordinator, walk):
    coordinator.add_physical_events(walk("ACD"))
    coordinator.inject_digital_preset(FULL_TRACE)


def test_evidence_json_contains_required_fields_and_serialises(coordinator, walk):
    phantom(coordinator, walk)
    ev = build_evidence(coordinator, NOW, image_file="x.png")
    data = json.loads(json.dumps(ev, ensure_ascii=False))
    for key in ("journey_id", "expected_procedure", "physical_trace", "digital_trace", "physical_events",
                "digital_events", "verdict", "violation_types", "violations", "step_states", "engine_version",
                "digital_simulated", "disclaimer", "generated_at_utc", "primary_finding"):
        assert key in data, key
    assert data["verdict"] == "VIOLATED" and data["violation_types"] == ["PHANTOM_COMPLETION"]
    assert data["physical_trace"] == ["A", "C", "D"]
    assert data["digital_trace"] == ["A", "B", "C", "D"]
    assert data["engine_version"] == "m0.1"
    assert data["journey_id"] == coordinator.active_journey_id
    assert [s["step_id"] for s in data["expected_procedure"]] == ["A", "B", "C", "D"]
    assert data["expected_procedure"][1]["name"] == "Credential Check"
    b = next(s for s in data["step_states"] if s["step_id"] == "B")
    assert (b["state"], b["indicator"]) == ("CONTRADICTORY", "CONFLICT")
    assert data["violations"][0]["finding"].startswith("Credential Check was recorded digitally")
    assert data["generated_at_utc"].endswith("+00:00")


def test_event_timestamps_and_channels_are_exact(coordinator, walk):
    phantom(coordinator, walk)
    data = build_evidence(coordinator, NOW)
    real = {e.event_id: e for e in coordinator.physical_events() + coordinator.digital_events()}
    listed = data["physical_events"] + data["digital_events"]
    assert len(listed) == len(real)
    for item in listed:
        src = real[item["event_id"]]
        assert datetime.fromisoformat(item["timestamp"]) == src.timestamp
        assert item["channel"] == src.source.value
    assert all(e["simulated"] is True and e["confidence"] is None for e in data["digital_events"])
    assert all(e["simulated"] is None and e["confidence"] is not None for e in data["physical_events"])


def test_digital_simulated_flag_and_disclaimer(coordinator, walk):
    coordinator.add_physical_events(walk("ABCD"))  # even with NO digital evidence the flag is true
    data = build_evidence(coordinator, NOW)
    assert data["digital_simulated"] is True
    assert "simulator" in data["disclaimer"] and "not an integration with a production checkpoint system" in data["disclaimer"]


def test_no_identity_or_biometric_fields(coordinator, walk):
    phantom(coordinator, walk)
    text = json.dumps(build_evidence(coordinator, NOW)).lower()
    for banned in ("face_", "biometric", "embedding", "tracker_id", "person_name", "identity"):
        assert banned not in text.replace("no persistent identity", "")


def test_naive_now_rejected(coordinator, walk):
    phantom(coordinator, walk)
    with pytest.raises(ValueError):
        build_evidence(coordinator, datetime(2026, 1, 1))


# snapshot orchestration
def test_save_snapshot_writes_png_and_json_side_by_side(coordinator, walk, tmp_path):
    phantom(coordinator, walk)
    paths = save_snapshot(coordinator, fake_png, tmp_path / "evidence", NOW)
    assert paths.png.name == "2026-10-17_172015_PHANTOM_COMPLETION.png"
    assert paths.json.name == "2026-10-17_172015_PHANTOM_COMPLETION.json"
    assert paths.png.exists() and paths.json.exists()
    data = json.loads(paths.json.read_text(encoding="utf-8"))
    assert data["image_file"] == paths.png.name and data["digital_simulated"] is True


def test_same_second_snapshots_do_not_overwrite(coordinator, walk, tmp_path):
    phantom(coordinator, walk)
    a = save_snapshot(coordinator, fake_png, tmp_path, NOW)
    b = save_snapshot(coordinator, fake_png, tmp_path, NOW)
    assert a.png != b.png and b.png.name.endswith("_PHANTOM_COMPLETION_2.png")


def test_snapshot_without_journey_is_refused_cleanly(coordinator, tmp_path):
    with pytest.raises(NoActiveJourneyError, match="Nothing to save"):
        save_snapshot(coordinator, fake_png, tmp_path, NOW)
    assert list(tmp_path.iterdir()) == []


def test_png_write_failure_is_reported_and_leaves_no_json(coordinator, walk, tmp_path):
    phantom(coordinator, walk)
    with pytest.raises(OSError):
        save_snapshot(coordinator, lambda p: False, tmp_path, NOW)
    assert list(tmp_path.glob("*.json")) == []
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}_\d{6}_PHANTOM_COMPLETION", snapshot_basename(NOW, "PHANTOM_COMPLETION"))
