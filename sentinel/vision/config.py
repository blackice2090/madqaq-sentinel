"""M1 live-vision configuration and human-readable error types."""
from __future__ import annotations

from dataclasses import dataclass

DEFAULT_MODEL = "yolo11n.pt"
DEFAULT_ZONES_PATH = "config/checkpoint_zones.json"
DEFAULT_PROCEDURE_ID = "generic-checkpoint-v1"
DEFAULT_ENTRY_ZONE_ID = "A"
EVENT_SOURCE_LABEL = "live_webcam"


class VisionError(Exception):
    """Base class. The message is always safe to show to the operator."""


class CameraError(VisionError):
    """Webcam missing, busy, invalid index, or stopped delivering frames."""


class ModelLoadError(VisionError):
    """The detection model could not be loaded."""


class ZoneConfigError(VisionError):
    """Zone configuration file missing or malformed."""


class MissingDependencyError(VisionError):
    """Optional vision dependencies are not installed."""


@dataclass(frozen=True)
class VisionConfig:
    camera_index: int = 0
    model: str = DEFAULT_MODEL
    zones_path: str = DEFAULT_ZONES_PATH
    confidence: float = 0.45
    procedure_id: str = DEFAULT_PROCEDURE_ID
    entry_zone_id: str = DEFAULT_ENTRY_ZONE_ID
    # A candidate zone must be held CONTINUOUSLY for this long (milliseconds)
    # before it becomes the stable zone and an event may be emitted.
    zone_dwell_ms: float = 600.0
    # Secondary safeguard: also require this many frames within the dwell time,
    # so a stalled/lagging stream cannot confirm a zone from one or two frames.
    min_consecutive_frames: int = 3
    # Per-tracker rolling window of ground points; the MEDIAN is used for zone
    # membership. 1 disables smoothing.
    smoothing_window: int = 5
    # Hysteresis: once stable in a zone, the point must leave that zone by more
    # than this normalized margin before the zone is considered left.
    boundary_margin: float = 0.02
    # Forget a tracker (not its journey record) after this long unseen.
    track_timeout_s: float = 10.0
    # Mirror the preview so on-screen motion matches the person's motion.
    mirror: bool = True
    # UI only: show the zone-stability diagnostics section in the demo.
    debug_zones: bool = False

    def validate(self) -> None:
        if isinstance(self.camera_index, bool) or not isinstance(self.camera_index, int) or self.camera_index < 0:
            raise VisionError(f"Invalid camera index {self.camera_index!r}: use a non-negative integer such as 0.")
        if not 0.0 < self.confidence <= 1.0:
            raise VisionError(f"Invalid confidence {self.confidence!r}: must be in (0, 1].")
        if self.zone_dwell_ms < 0:
            raise VisionError("zone_dwell_ms must be >= 0.")
        if self.smoothing_window < 1:
            raise VisionError("smoothing_window must be >= 1.")
        if not 0.0 <= self.boundary_margin < 0.25:
            raise VisionError("boundary_margin must be in [0, 0.25).")
        if self.min_consecutive_frames < 1:
            raise VisionError("min_consecutive_frames must be >= 1.")
        if self.track_timeout_s <= 0:
            raise VisionError("track_timeout_s must be > 0.")
