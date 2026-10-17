"""OpenCV rendering for the M1 live demo. Needs cv2; not used by unit tests.

NOTE: OpenCV's built-in fonts are ASCII-only, so traces are drawn "A -> B -> C".
"""
from __future__ import annotations

from typing import Any

from sentinel.domain.models import JourneyStatus
from sentinel.vision.pipeline import FrameResult, JourneySummary
from sentinel.vision.zones import ZoneSet, to_pixels

# Project palette, BGR order for OpenCV.
GREEN = (60, 63, 14)      # #0E3F3C deep green
CREAM = (231, 241, 247)   # #F7F1E7 cream
ORANGE = (74, 120, 217)   # #D9784A orange
PANEL_W = 400
FONT = 0  # cv2.FONT_HERSHEY_SIMPLEX


def _text(cv2: Any, img: Any, s: str, org: tuple[int, int], scale: float = 0.5, color=CREAM, thick: int = 1) -> None:
    cv2.putText(img, s, org, FONT, scale, color, thick, cv2.LINE_AA)


def _wrap(cv2: Any, text: str, max_w: int, scale: float, thick: int = 1) -> list[str]:
    lines: list[str] = []
    cur = ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if cv2.getTextSize(trial, FONT, scale, thick)[0][0] <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def draw_scene(cv2: Any, frame: Any, zones: ZoneSet, result: FrameResult, debug: bool = False,
               focus_tracker_id: int | None = None) -> None:
    h, w = frame.shape[:2]
    active = {p.zone_id for p in result.persons if p.zone_id}
    layer = frame.copy()
    for z in zones:
        x1, y1, x2, y2 = to_pixels(z.box, w, h)
        cv2.rectangle(layer, (x1, y1), (x2, y2), GREEN, -1)
    cv2.addWeighted(layer, 0.30, frame, 0.70, 0, frame)
    for z in zones:
        x1, y1, x2, y2 = to_pixels(z.box, w, h)
        on = z.zone_id in active
        cv2.rectangle(frame, (x1, y1), (x2, y2), ORANGE if on else CREAM, 3 if on else 1)
        label = z.label
        (tw, th), _ = cv2.getTextSize(label, FONT, 0.5, 1)
        ly = min(h - 6, y1 + th + 8)
        cv2.rectangle(frame, (x1, ly - th - 6), (x1 + tw + 8, ly + 4), GREEN, -1)
        _text(cv2, frame, label, (x1 + 4, ly), 0.5, CREAM)
    for p in result.persons:
        x1, y1, x2, y2 = to_pixels(p.box, w, h)
        color = ORANGE if p.journey_id else CREAM
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.circle(frame, ((x1 + x2) // 2, y2 - 2), 5, color, -1)  # ground point
        tag = f"ID {p.tracker_id}  {p.confidence:.2f}"
        (tw, th), _ = cv2.getTextSize(tag, FONT, 0.5, 1)
        ty = max(th + 6, y1)
        cv2.rectangle(frame, (x1, ty - th - 6), (x1 + tw + 8, ty + 2), GREEN, -1)
        _text(cv2, frame, tag, (x1 + 4, ty - 3), 0.5, color)
    if debug:
        _draw_debug(cv2, frame, result, focus_tracker_id)
    # header, top-left
    cv2.rectangle(frame, (0, 0), (330, 52), GREEN, -1)
    _text(cv2, frame, "MADQAQ Sentinel", (10, 22), 0.7, CREAM, 2)
    _text(cv2, frame, "Live Physical Perception - M1", (10, 42), 0.5, ORANGE)


def draw_panel(cv2: Any, np: Any, height: int, summary: JourneySummary | None, zones: ZoneSet, notice: str = "") -> Any:
    panel = np.full((height, PANEL_W, 3), GREEN, dtype=np.uint8)
    x, y = 16, 30
    _text(cv2, panel, "JOURNEY STATUS", (x, y), 0.6, ORANGE, 2)
    y += 30

    def row(label: str, value: str, color=CREAM) -> None:
        nonlocal y
        _text(cv2, panel, label, (x, y), 0.45, ORANGE)
        y += 20
        for line in _wrap(cv2, value, PANEL_W - 2 * x, 0.55, 1) or [""]:
            _text(cv2, panel, line, (x, y), 0.55, color)
            y += 22
        y += 6

    if summary is None:
        row("Journey ID", "-- none yet --")
        row("Physical trace", "(enter Zone A to begin)")
        row("Current zone", "--")
        row("Physical events emitted", "0")
        row("Latest event", "--")
        row("M0 conformance", "NO JOURNEY")
    else:
        zone = zones.get(summary.current_zone).label if summary.current_zone else "outside zones"
        latest = "--"
        if summary.latest_event is not None:
            e = summary.latest_event
            latest = f"{zones.get(e.step_id).label} @ {e.timestamp:%H:%M:%S}Z"
        row("Journey ID (temporary)", summary.journey_id[:8])
        row("Physical trace", " -> ".join(summary.trace) or "--", CREAM)
        row("Current zone", zone)
        row("Physical events emitted", str(summary.event_count))
        row("Latest event", latest)
        bad = summary.m0_status == JourneyStatus.VIOLATED
        row("M0 conformance", summary.headline, ORANGE if bad else CREAM)
        row("M0 status / reason", f"{summary.m0_status.value}: {summary.reason}", ORANGE if bad else CREAM)
        for line in summary.violation_lines:
            row("Finding", line, ORANGE)
    if notice:
        _text(cv2, panel, notice, (x, height - 62), 0.45, ORANGE)
    _text(cv2, panel, "Q / ESC quit    R reset", (x, height - 40), 0.45, CREAM)
    _text(cv2, panel, "Physical channel only. No identity stored.", (x, height - 18), 0.4, CREAM)
    return panel


def _fmt_zone(z: str | None) -> str:
    return z if z else "outside"


def _draw_debug(cv2: Any, frame: Any, result: FrameResult, focus_tracker_id: int | None) -> None:
    """--debug-zones: smoothed point markers for everyone, text for one person."""
    h, w = frame.shape[:2]
    for p in result.persons:
        if p.debug is None:
            continue
        sx, sy = round(p.debug.smoothed_point[0] * w), round(p.debug.smoothed_point[1] * h)
        cv2.drawMarker(frame, (sx, min(sy, h - 1)), CREAM, cv2.MARKER_CROSS, 14, 2)
    chosen = next((p for p in result.persons if p.tracker_id == focus_tracker_id and p.debug), None) \
        or next((p for p in result.persons if p.debug), None)
    if chosen is None:
        lines = ["DEBUG ZONES: no person tracked"]
    else:
        d = chosen.debug
        lines = [
            f"DEBUG ZONES  (tracker {chosen.tracker_id})",
            f"Raw zone: {_fmt_zone(d.raw_zone)}",
            f"Candidate zone: {_fmt_zone(d.candidate_zone)}",
            f"Stable zone: {_fmt_zone(d.stable_zone)}",
            f"Dwell: {d.dwell_ms:.0f} / {d.dwell_target_ms:.0f} ms",
            f"Smoothed ground point: {d.smoothed_point[0]:.3f}, {d.smoothed_point[1]:.3f}",
        ]
    line_h = 18
    box_h = line_h * len(lines) + 10
    y0 = h - box_h - 6
    layer = frame.copy()
    cv2.rectangle(layer, (6, y0), (330, h - 6), GREEN, -1)
    cv2.addWeighted(layer, 0.80, frame, 0.20, 0, frame)
    for i, line in enumerate(lines):
        _text(cv2, frame, line, (12, y0 + 18 + i * line_h), 0.45, ORANGE if i == 0 else CREAM)
