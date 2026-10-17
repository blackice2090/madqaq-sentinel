"""M1 live physical perception. Heavy dependencies (cv2, ultralytics) are imported lazily."""
from sentinel.vision.config import (
    CameraError, MissingDependencyError, ModelLoadError, VisionConfig, VisionError, ZoneConfigError,
)
from sentinel.vision.event_emitter import PhysicalEventEmitter
from sentinel.vision.pipeline import PerceptionPipeline
from sentinel.vision.tracker import TrackedPerson
from sentinel.vision.zones import Zone, ZoneSet

__all__ = [
    "CameraError", "MissingDependencyError", "ModelLoadError", "VisionConfig", "VisionError",
    "ZoneConfigError", "PhysicalEventEmitter", "PerceptionPipeline", "TrackedPerson", "Zone", "ZoneSet",
]
