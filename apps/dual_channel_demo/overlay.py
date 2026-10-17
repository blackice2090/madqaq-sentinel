"""M2 status panel (OpenCV). Reuses the M1 scene drawing and palette. ASCII-only text."""
from __future__ import annotations

from typing import Any

from apps.vision_demo.overlay import CREAM, FONT, GREEN, ORANGE, _text, _wrap
from sentinel.domain.models import JourneyStatus, StepState
from sentinel.dual_channel.state import DualChannelSummary

PANEL_W = 470
MIN_HEIGHT = 540
SIM_BANNER = "SIMULATED DIGITAL CHANNEL"
SIM_NOTE = "local simulator - not a real checkpoint system"

_STATE_WORD = {
    StepState.CONFIRMED: "OK", StepState.UNCERTAIN: "1-CH", StepState.INCOMPLETE: "MISSING",
    StepState.CONTRADICTORY: "CONFLICT", StepState.NOT_REACHED: "-",
}
CONTROLS = ("1 digital full   2 digital without B   3 digital B failed",
            "0 clear digital   R reset all   Q/ESC quit")


def _trace(parts: list[str]) -> str:
    return " -> ".join(parts) if parts else "--"


def draw_dual_panel(cv2: Any, np: Any, height: int, summary: DualChannelSummary | None, notice: str = "") -> tuple[Any, int]:
    """Return (panel image, y of the last content line) so layout can be checked."""
    height = max(height, MIN_HEIGHT)
    panel = np.full((height, PANEL_W, 3), GREEN, dtype=np.uint8)
    x = 16
    y = 26
    _text(cv2, panel, "DUAL-CHANNEL INTEGRATION - M2", (x, y), 0.55, CREAM, 2)
    y += 12
    cv2.rectangle(panel, (x - 6, y), (PANEL_W - 10, y + 40), ORANGE, -1)
    _text(cv2, panel, SIM_BANNER, (x, y + 19), 0.62, GREEN, 2)
    _text(cv2, panel, SIM_NOTE, (x, y + 35), 0.4, GREEN, 1)
    y += 62

    def row(label: str, value: str, color=CREAM, scale: float = 0.55) -> None:
        nonlocal y
        _text(cv2, panel, label, (x, y), 0.4, ORANGE)
        y += 19
        for line in _wrap(cv2, value, PANEL_W - 2 * x, scale) or [""]:
            _text(cv2, panel, line, (x, y), scale, color)
            y += 21
        y += 3

    if summary is None:
        row("EXPECTED", "A -> B -> C -> D")
        row("PHYSICAL  (live camera)", "--")
        row("DIGITAL  (SIMULATED)", "--")
        row("VERDICT", "NO JOURNEY", ORANGE, 0.8)
        row("FINDING", "Enter Zone A to begin a journey.")
    else:
        bad = summary.status == JourneyStatus.VIOLATED
        steps = "  ".join(f"{sid} {_STATE_WORD[st]}" for sid, st in summary.step_states)
        row("EXPECTED", _trace(summary.expected))
        row("PHYSICAL  (live camera)", _trace(summary.physical_trace))
        row("DIGITAL  (SIMULATED)", _trace(summary.digital_trace))
        row("STEP STATES", steps, CREAM, 0.48)
        row(f"VERDICT  (journey {summary.journey_id[:8]})", summary.status.value, ORANGE if bad else CREAM, 0.8)
        finding = summary.finding
        if summary.finding_codes:
            _text(cv2, panel, "FINDING", (x, y), 0.4, ORANGE)
            y += 19
            _text(cv2, panel, ", ".join(dict.fromkeys(summary.finding_codes)), (x, y), 0.6, ORANGE, 2)
            y += 24
            for line in _wrap(cv2, finding, PANEL_W - 2 * x, 0.45):
                _text(cv2, panel, line, (x, y), 0.45, CREAM)
                y += 19
        else:
            row("FINDING", finding, CREAM, 0.5)
    last_content_y = y
    base = height - 14
    for i, line in enumerate(reversed(CONTROLS)):
        _text(cv2, panel, line, (x, base - i * 18), 0.42, CREAM)
    if notice:
        for i, line in enumerate(reversed(_wrap(cv2, notice, PANEL_W - 2 * x, 0.45))):
            _text(cv2, panel, line, (x, base - len(CONTROLS) * 18 - 8 - i * 18), 0.45, ORANGE)
    return panel, last_content_y
