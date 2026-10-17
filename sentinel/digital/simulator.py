"""Local digital-event simulator (demo only).

Every event it creates is DIGITAL, carries metadata marking it as simulated, uses a
UUID event id and a timezone-aware UTC timestamp, and binds to the journey/procedure
it is given. It contains no personal identity.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Callable

from sentinel.digital.presets import DigitalPreset
from sentinel.domain.models import EventType, EvidenceSource, NormalizedEvent

SIMULATOR_SOURCE = "m2_digital_simulator"


class DigitalEventSimulator:
    def __init__(self, step_ms: int = 50, clock: Callable[[], datetime] | None = None):
        if step_ms < 1:
            raise ValueError("step_ms must be >= 1")
        self.step_ms = step_ms
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def build_events(self, preset: DigitalPreset, journey_id: str, procedure_id: str) -> list[NormalizedEvent]:
        """Events for `preset`, in preset order, with strictly increasing timestamps.

        The last event is stamped "now"; earlier ones are `step_ms` apart before it, so
        no timestamp lies in the future and the preset order survives the engine's
        timestamp ordering.
        """
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("simulator clock must return timezone-aware datetimes")
        n = len(preset.steps)
        events = []
        for i, (step_id, completed) in enumerate(preset.steps):
            events.append(NormalizedEvent(
                event_id=str(uuid.uuid4()),
                journey_id=journey_id,
                procedure_id=procedure_id,
                source=EvidenceSource.DIGITAL,
                event_type=EventType.STEP_COMPLETED if completed else EventType.STEP_FAILED,
                step_id=step_id,
                timestamp=now - timedelta(milliseconds=self.step_ms * (n - 1 - i)),
                confidence=1.0,
                metadata={"source": SIMULATOR_SOURCE, "simulated": True},
            ))
        return events
