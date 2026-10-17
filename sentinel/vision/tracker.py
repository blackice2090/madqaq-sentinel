"""Temporary person tracking (ByteTrack via Ultralytics).

Tracker IDs are temporary, in-memory integers. No appearance embeddings, faces
or re-identification are computed or stored.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from sentinel.vision.config import VisionError
from sentinel.vision.detector import PersonDetector
from sentinel.vision.zones import Box, Point, ground_point


@dataclass(frozen=True)
class TrackedPerson:
    """One tracked person in one frame. `box` is normalized (x1, y1, x2, y2)."""

    tracker_id: int
    confidence: float
    box: Box

    @property
    def ground_point(self) -> Point:
        return ground_point(self.box)


class PersonTracker(Protocol):
    def update(self, frame: Any) -> list[TrackedPerson]: ...
    def reset(self) -> None: ...


class UltralyticsByteTrackTracker:
    """Detection + ByteTrack in one Ultralytics call, person class only."""

    def __init__(self, detector: PersonDetector):
        self._detector = detector

    @classmethod
    def load(cls, model_name: str, confidence: float) -> "UltralyticsByteTrackTracker":
        return cls(PersonDetector.load(model_name, confidence))

    def update(self, frame: Any) -> list[TrackedPerson]:
        d = self._detector
        try:
            results = d.model.track(
                frame, persist=True, tracker="bytetrack.yaml",
                classes=d.person_class_ids, conf=d.confidence, verbose=False,
            )
        except Exception as exc:
            raise VisionError(f"Detection/tracking failed on a frame: {exc}") from exc
        people: list[TrackedPerson] = []
        for result in results:
            boxes = result.boxes
            if boxes is None or boxes.id is None:  # nothing tracked yet
                continue
            xyxyn = boxes.xyxyn.cpu().tolist()
            confs = boxes.conf.cpu().tolist()
            ids = boxes.id.int().cpu().tolist()
            for box, conf, tid in zip(xyxyn, confs, ids):
                x1, y1, x2, y2 = (min(1.0, max(0.0, float(v))) for v in box)
                people.append(TrackedPerson(int(tid), min(1.0, max(0.0, float(conf))), (x1, y1, x2, y2)))
        return people

    def reset(self) -> None:
        """Forget current tracks (new temporary IDs will be issued)."""
        predictor = getattr(self._detector.model, "predictor", None)
        for t in getattr(predictor, "trackers", None) or []:
            try:
                t.reset()
            except Exception:
                pass
