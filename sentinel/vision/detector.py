"""Person detector: loads a lightweight Ultralytics YOLO model (person class only).

Ultralytics is an OPTIONAL dependency and is imported lazily. Weights are
obtained locally by Ultralytics on first use and are never committed.
"""
from __future__ import annotations

from typing import Any

from sentinel.vision.config import MissingDependencyError, ModelLoadError


class PersonDetector:
    """Holds the loaded model and the class ids that mean 'person'."""

    def __init__(self, model: Any, person_class_ids: list[int], confidence: float):
        self.model = model
        self.person_class_ids = person_class_ids
        self.confidence = confidence

    @classmethod
    def load(cls, model_name: str, confidence: float) -> "PersonDetector":
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise MissingDependencyError(
                "Vision dependencies are not installed. Run:  pip install -e \".[vision]\"  "
                "(installs opencv-python and ultralytics)."
            ) from exc
        try:
            model = YOLO(model_name)
        except Exception as exc:  # download failure, bad path, corrupt weights, ...
            raise ModelLoadError(
                f"Could not load detection model '{model_name}': {exc}. "
                "Check the model name/path; first use needs internet access to fetch the weights."
            ) from exc
        names = getattr(model, "names", None) or {}
        ids = [int(i) for i, n in names.items() if str(n).lower() == "person"]
        if not ids:
            raise ModelLoadError(f"Model '{model_name}' has no 'person' class; use a COCO-trained model such as yolo11n.pt.")
        return cls(model, ids, confidence)
