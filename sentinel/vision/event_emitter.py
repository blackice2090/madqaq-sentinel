"""Zone-transition logic -> PHYSICAL NormalizedEvents. Pure Python, no camera.

Perception de-noising (M1 only; the M0 engine is never altered)
---------------------------------------------------------------
1. Smoothing   : zone membership uses the MEDIAN of the last `smoothing_window`
                 ground points of that tracker, not the raw one-frame point.
2. Hysteresis  : once stable in a zone, the smoothed point must leave that zone
                 by more than `boundary_margin` (normalized) before it counts as
                 left. Zones themselves never overlap; the margin only widens
                 the CURRENT stable zone for the "stay" test.
3. Dwell       : a candidate zone must be held continuously for `zone_dwell_ms`
                 (time-based, plus `min_consecutive_frames` as a safeguard). If
                 the candidate changes first, the timer restarts.
4. First visit : within one journey each procedure step is emitted at most once,
                 in the order of FIRST stable visits. Nothing is sorted or
                 invented: A -> C -> B is emitted as A -> C -> B so M0 can see
                 the order inversion; only repeats of an already-emitted step
                 are suppressed.

Journeys
--------
* A tracker must be stable in the entry zone (A) to start a journey. A tracker
  first stable elsewhere gets no journey and produces no events.
* Journey IDs are random UUIDs held only in memory (tracker_id -> journey_id).
* No identity is stored: only the temporary tracker id and a random journey id.
"""
from __future__ import annotations

import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import median

from sentinel.domain.models import EventType, EvidenceSource, NormalizedEvent
from sentinel.vision.config import EVENT_SOURCE_LABEL, VisionConfig
from sentinel.vision.tracker import TrackedPerson
from sentinel.vision.zones import Point, ZoneSet


@dataclass(frozen=True)
class TrackerDebug:
    """Per-tracker diagnostics for the --debug-zones overlay."""

    raw_zone: str | None         # zone of the raw one-frame ground point
    candidate_zone: str | None   # zone currently being timed
    stable_zone: str | None      # dwell-confirmed zone
    dwell_ms: float              # time the candidate has been held (0 if it equals stable)
    dwell_target_ms: float
    raw_point: Point
    smoothed_point: Point


@dataclass
class _TrackerState:
    last_seen: datetime
    history: deque
    journey_id: str | None = None
    stable_zone: str | None = None
    candidate_zone: str | None = None
    candidate_since: datetime | None = None
    candidate_frames: int = 0
    candidate_conf_sum: float = 0.0
    debug: TrackerDebug | None = None


@dataclass
class JourneyRecord:
    journey_id: str
    tracker_id: int
    started_at: datetime
    events: list[NormalizedEvent] = field(default_factory=list)
    emitted_steps: set[str] = field(default_factory=set)
    current_zone: str | None = None


class PhysicalEventEmitter:
    def __init__(self, zones: ZoneSet, procedure_id: str, config: VisionConfig | None = None):
        self.zones = zones
        self.procedure_id = procedure_id
        self.config = config or VisionConfig()
        self.config.validate()
        if self.config.entry_zone_id not in zones.ids:
            raise ValueError(f"entry zone '{self.config.entry_zone_id}' is not defined in the zone config")
        self._trackers: dict[int, _TrackerState] = {}
        self._journeys: dict[str, JourneyRecord] = {}

    # ---- public state ----------------------------------------------------
    @property
    def journeys(self) -> dict[str, JourneyRecord]:
        return self._journeys

    def journey_for_tracker(self, tracker_id: int) -> str | None:
        st = self._trackers.get(tracker_id)
        return st.journey_id if st else None

    def zone_for_tracker(self, tracker_id: int) -> str | None:
        st = self._trackers.get(tracker_id)
        return st.stable_zone if st else None

    def debug_for_tracker(self, tracker_id: int) -> TrackerDebug | None:
        st = self._trackers.get(tracker_id)
        return st.debug if st else None

    def all_events(self) -> list[NormalizedEvent]:
        return [e for j in self._journeys.values() for e in j.events]

    def reset(self) -> None:
        """Clear trackers, smoothing history, journeys and emitted-step suppression."""
        self._trackers.clear()
        self._journeys.clear()

    # ---- processing ------------------------------------------------------
    def process(self, persons: list[TrackedPerson], now: datetime | None = None) -> list[NormalizedEvent]:
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        cfg = self.config
        emitted: list[NormalizedEvent] = []
        seen: set[int] = set()

        for person in persons:
            tid = person.tracker_id
            seen.add(tid)
            st = self._trackers.get(tid)
            if st is None:
                st = self._trackers[tid] = _TrackerState(last_seen=now, history=deque(maxlen=cfg.smoothing_window))
            st.last_seen = now

            raw = person.ground_point
            st.history.append(raw)
            smoothed: Point = (median(p[0] for p in st.history), median(p[1] for p in st.history))
            raw_zone = self.zones.locate(raw)
            observed = self._observe(smoothed, st.stable_zone)

            if st.candidate_since is None or observed != st.candidate_zone:
                st.candidate_zone, st.candidate_since = observed, now  # (re)start the dwell timer
                st.candidate_frames, st.candidate_conf_sum = 1, person.confidence
            else:
                st.candidate_frames += 1
                st.candidate_conf_sum += person.confidence

            dwell_ms = (now - st.candidate_since).total_seconds() * 1000.0
            if (st.candidate_zone != st.stable_zone and dwell_ms >= cfg.zone_dwell_ms
                    and st.candidate_frames >= cfg.min_consecutive_frames):
                st.stable_zone = st.candidate_zone
                if st.journey_id is not None:
                    self._journeys[st.journey_id].current_zone = st.stable_zone
                if st.stable_zone is not None:
                    event = self._on_stable_enter(st, tid, st.stable_zone, st.candidate_conf_sum / st.candidate_frames, now)
                    if event is not None:
                        emitted.append(event)

            st.debug = TrackerDebug(
                raw_zone=raw_zone.zone_id if raw_zone else None,
                candidate_zone=st.candidate_zone,
                stable_zone=st.stable_zone,
                dwell_ms=0.0 if st.candidate_zone == st.stable_zone else dwell_ms,
                dwell_target_ms=cfg.zone_dwell_ms,
                raw_point=raw,
                smoothed_point=smoothed,
            )

        self._prune(seen, now)
        return emitted

    def _observe(self, point: Point, stable_zone: str | None) -> str | None:
        """Zone of `point`, with hysteresis toward the current stable zone."""
        m = self.config.boundary_margin
        if stable_zone is not None and m > 0:
            z = self.zones.get(stable_zone)
            if z.x1 - m <= point[0] <= z.x2 + m and z.y1 - m <= point[1] <= z.y2 + m:
                return stable_zone
        zone = self.zones.locate(point)
        return zone.zone_id if zone else None

    def _on_stable_enter(self, st: _TrackerState, tracker_id: int, zone_id: str, conf: float, now: datetime) -> NormalizedEvent | None:
        if st.journey_id is None:
            if zone_id != self.config.entry_zone_id:
                return None  # joined mid-procedure: never silently start a normal journey
            st.journey_id = str(uuid.uuid4())
            self._journeys[st.journey_id] = JourneyRecord(st.journey_id, tracker_id, started_at=now)
            self._journeys[st.journey_id].current_zone = zone_id
        rec = self._journeys[st.journey_id]
        if zone_id in rec.emitted_steps:
            return None  # step already emitted for this journey: boundary jitter / re-entry
        event = NormalizedEvent(
            event_id=f"{rec.journey_id}-P{len(rec.events) + 1:03d}-{zone_id}",
            journey_id=rec.journey_id,
            procedure_id=self.procedure_id,
            source=EvidenceSource.PHYSICAL,
            event_type=EventType.STEP_OBSERVED,
            step_id=zone_id,
            timestamp=now,
            confidence=min(1.0, max(0.0, conf)),
            metadata={"tracker_id": tracker_id, "zone": zone_id, "source": EVENT_SOURCE_LABEL},
        )
        rec.events.append(event)
        rec.emitted_steps.add(zone_id)
        return event

    def _prune(self, seen: set[int], now: datetime) -> None:
        timeout = self.config.track_timeout_s
        for tid in [t for t, s in self._trackers.items() if t not in seen and (now - s.last_seen).total_seconds() > timeout]:
            st = self._trackers.pop(tid)
            if st.journey_id is not None:
                self._journeys[st.journey_id].current_zone = None
