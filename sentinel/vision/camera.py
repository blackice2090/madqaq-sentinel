"""Webcam capture (OpenCV, imported lazily). Frames are processed in memory only; never saved."""
from __future__ import annotations

import sys
from typing import Any

from sentinel.vision.config import CameraError, MissingDependencyError


def import_cv2():
    try:
        import cv2
    except ImportError as exc:
        raise MissingDependencyError(
            "OpenCV is not installed. Run:  pip install -e \".[vision]\"  (installs opencv-python and ultralytics)."
        ) from exc
    return cv2


class Camera:
    def __init__(self, capture: Any, index: int, max_read_failures: int = 30):
        self._cap = capture
        self.index = index
        self._max_failures = max_read_failures
        self._failures = 0

    @classmethod
    def open(cls, index: int, max_read_failures: int = 30) -> "Camera":
        if isinstance(index, bool) or not isinstance(index, int) or index < 0:
            raise CameraError(f"Invalid camera index {index!r}: use a non-negative integer such as 0.")
        cv2 = import_cv2()
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW) if sys.platform == "win32" else cv2.VideoCapture(index)
        if not cap.isOpened():
            cap.release()
            cap = cv2.VideoCapture(index)  # fall back to the default backend
        if not cap.isOpened():
            cap.release()
            raise CameraError(
                f"Could not open camera {index}. Check that a webcam is connected, not in use by another app, "
                "camera access is allowed for this program, and try another index with --camera 1."
            )
        return cls(cap, index, max_read_failures)

    def read(self) -> Any:
        """Return one BGR frame. Tolerates brief hiccups; raises CameraError if the stream is dead."""
        ok, frame = self._cap.read()
        if ok and frame is not None:
            self._failures = 0
            return frame
        self._failures += 1
        if self._failures >= self._max_failures:
            raise CameraError(f"Camera {self.index} stopped delivering frames (was it unplugged or taken by another app?).")
        return None

    def release(self) -> None:
        self._cap.release()

    def __enter__(self) -> "Camera":
        return self

    def __exit__(self, *exc: object) -> None:
        self.release()
