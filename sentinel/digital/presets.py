"""Named digital-trace presets for the M2 demo. Each is an ordered list of (step_id, completed)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DigitalPreset:
    preset_id: str
    key: str          # keyboard key in the live demo
    title: str
    steps: tuple[tuple[str, bool], ...]  # (step_id, completed?) ; completed=False -> STEP_FAILED


FULL_TRACE = DigitalPreset(
    "full_trace", "1", "FULL DIGITAL TRACE (A,B,C,D completed)",
    (("A", True), ("B", True), ("C", True), ("D", True)),
)
WITHOUT_B = DigitalPreset(
    "without_b", "2", "DIGITAL TRACE WITHOUT B (A,C,D completed)",
    (("A", True), ("C", True), ("D", True)),
)
B_FAILED = DigitalPreset(
    "b_failed", "3", "DIGITAL TRACE WITH B FAILED (A,C,D completed; B failed)",
    (("A", True), ("B", False), ("C", True), ("D", True)),
)

PRESETS: dict[str, DigitalPreset] = {p.preset_id: p for p in (FULL_TRACE, WITHOUT_B, B_FAILED)}
PRESETS_BY_KEY: dict[str, DigitalPreset] = {p.key: p for p in PRESETS.values()}
