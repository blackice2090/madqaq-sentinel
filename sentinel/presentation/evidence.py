"""Evidence snapshot: filename generation + JSON evidence summary (+ orchestration of the PNG write).

Contains no face crops and no identity: only event traces, timestamps, the verdict and the
engine version. The PNG is whatever dashboard image the caller hands in (the user-triggered
screenshot of the local demo).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from sentinel.domain.models import EvidenceSource, NormalizedEvent
from sentinel.dual_channel import DualChannelCoordinator
from sentinel.dual_channel.state import NoActiveJourneyError
from sentinel.presentation import labels

SCHEMA = "madqaq-sentinel-evidence/1"
DEFAULT_DIR = "artifacts/evidence"


def snapshot_slug(coordinator: DualChannelCoordinator) -> str:
    s = coordinator.summary()
    return "_".join(dict.fromkeys(s.finding_codes)) if s.finding_codes else s.status.value


def snapshot_basename(now: datetime, slug: str) -> str:
    """e.g. 2026-10-17_172015_PHANTOM_COMPLETION (no extension)."""
    safe = "".join(c if c.isalnum() or c == "_" else "_" for c in slug).strip("_") or "EVIDENCE"
    return f"{now:%Y-%m-%d_%H%M%S}_{safe}"


def _event_dict(e: NormalizedEvent, names: dict[str, str]) -> dict:
    physical = e.source == EvidenceSource.PHYSICAL
    return {
        "event_id": e.event_id,
        "timestamp": e.timestamp.isoformat(),
        "channel": e.source.value,
        "step_id": e.step_id,
        "step_name": names.get(e.step_id, e.step_id),
        "event_type": e.event_type.value,
        "confidence": e.confidence if physical else None,
        "simulated": None if physical else bool(e.metadata.get("simulated")),
    }


def build_evidence(coordinator: DualChannelCoordinator, now: datetime | None = None,
                   image_file: str | None = None) -> dict:
    """JSON-serialisable evidence summary of the ACTIVE journey, taken from real runtime state."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    summary = coordinator.summary()
    result = coordinator.result()
    proc = coordinator.procedure
    names = labels.step_names(proc)
    physical = coordinator.physical_events()
    digital = coordinator.digital_events()
    viol_by_step = {}
    for v in result.violations:
        viol_by_step.setdefault(v.step_id, v.type)
    return {
        "schema": SCHEMA,
        "generated_at_utc": now.astimezone(timezone.utc).isoformat(),
        "image_file": image_file,
        "journey_id": summary.journey_id,
        "procedure_id": proc.procedure_id,
        "expected_procedure": [{"step_id": sid, "name": nm} for sid, nm in names.items()],
        "physical_trace": [e.step_id for e in physical],
        "digital_trace": summary.digital_trace,
        "physical_events": [_event_dict(e, names) for e in physical],
        "digital_events": [_event_dict(e, names) for e in digital],
        "verdict": result.overall_status.value,
        "violation_types": [v.type.value for v in result.violations],
        "violations": [{
            "type": v.type.value,
            "label": labels.violation_label(v.type),
            "step_id": v.step_id,
            "finding": labels.human_finding(v, names),
            "engine_message": v.message,
        } for v in result.violations],
        "primary_finding": labels.primary_finding(result.overall_status, result.violations, names),
        "step_states": [{
            "step_id": sa.step_id,
            "name": names[sa.step_id],
            "state": sa.state.value,
            "indicator": labels.step_state_view(sa.state, viol_by_step.get(sa.step_id))[0],
        } for sa in result.step_states],
        "engine_version": result.engine_version,
        "digital_simulated": True,
        "disclaimer": labels.SIM_DISCLAIMER_LONG,
        "privacy": labels.PRIVACY_FOOTER,
    }


@dataclass(frozen=True)
class SnapshotPaths:
    png: Path
    json: Path


def _free_base(out_dir: Path, base: str) -> str:
    candidate, n = base, 1
    while (out_dir / f"{candidate}.png").exists() or (out_dir / f"{candidate}.json").exists():
        n += 1
        candidate = f"{base}_{n}"
    return candidate


def save_snapshot(
    coordinator: DualChannelCoordinator,
    write_png: Callable[[Path], bool],
    out_dir: str | Path = DEFAULT_DIR,
    now_local: datetime | None = None,
) -> SnapshotPaths:
    """Write <timestamp>_<VERDICT>.png (via `write_png`) and a JSON summary beside it.

    Raises NoActiveJourneyError when there is nothing to record, and OSError if a file cannot be written.
    """
    if coordinator.active_journey_id is None:
        raise NoActiveJourneyError("Nothing to save yet: no journey. Enter Zone A first.")
    now_local = now_local or datetime.now().astimezone()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    base = _free_base(out, snapshot_basename(now_local, snapshot_slug(coordinator)))
    png, js = out / f"{base}.png", out / f"{base}.json"
    if not write_png(png):
        raise OSError(f"Could not write the screenshot to {png}.")
    evidence = build_evidence(coordinator, now_local.astimezone(timezone.utc), image_file=png.name)
    js.write_text(json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8")
    return SnapshotPaths(png, js)
