"""Evidence timeline built ONLY from real runtime events (nothing is generated for visual completeness)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, tzinfo

from sentinel.domain.models import EvidenceSource, NormalizedEvent
from sentinel.presentation.labels import event_word

DEFAULT_LIMIT = 8


@dataclass(frozen=True)
class TimelineEntry:
    event_id: str
    timestamp: datetime
    time_text: str
    channel: str            # "PHYSICAL" | "DIGITAL"
    step_id: str
    step_name: str
    event_text: str         # "observed" | "completed" | "failed"
    confidence: float | None  # physical events only
    simulated: bool         # True for simulator-produced digital events

    @property
    def detail(self) -> str:
        """Right-hand text of a timeline row."""
        if self.confidence is not None:
            return f"{self.event_text} · conf {self.confidence:.2f}"
        return f"{self.event_text} (simulated)" if self.simulated else self.event_text


def format_time(ts: datetime, tz: tzinfo | None = None) -> str:
    """HH:MM:SS in `tz`, or in the machine's local timezone when tz is None."""
    return ts.astimezone(tz).strftime("%H:%M:%S")


def build_timeline(
    physical: list[NormalizedEvent],
    digital: list[NormalizedEvent],
    names: dict[str, str],
    limit: int = DEFAULT_LIMIT,
    tz: tzinfo | None = None,
) -> list[TimelineEntry]:
    """Chronological (oldest first) merge of the two channels; only the latest `limit` entries are kept.

    Ties keep physical before digital, then arrival order. Events are only read, never changed.
    """
    tagged = [(e, 0, i) for i, e in enumerate(physical)] + [(e, 1, i) for i, e in enumerate(digital)]
    tagged.sort(key=lambda t: (t[0].timestamp, t[1], t[2]))
    entries = [
        TimelineEntry(
            event_id=e.event_id,
            timestamp=e.timestamp,
            time_text=format_time(e.timestamp, tz),
            channel="PHYSICAL" if e.source == EvidenceSource.PHYSICAL else "DIGITAL",
            step_id=e.step_id,
            step_name=names.get(e.step_id, e.step_id),
            event_text=event_word(e.event_type),
            confidence=e.confidence if e.source == EvidenceSource.PHYSICAL else None,
            simulated=bool(e.metadata.get("simulated")) if e.source == EvidenceSource.DIGITAL else False,
        )
        for e, _, _ in tagged
    ]
    return entries[-limit:] if limit > 0 else []
