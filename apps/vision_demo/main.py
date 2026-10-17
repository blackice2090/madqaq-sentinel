"""M1 live physical-perception demo.

    python -m apps.vision_demo.main [--camera 0] [--model yolo11n.pt]
                                    [--zones config/checkpoint_zones.json] [--confidence 0.45]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sentinel.conformance.engine import ConformanceEngine
from sentinel.vision.camera import Camera, import_cv2
from sentinel.vision.config import (
    DEFAULT_MODEL, DEFAULT_ZONES_PATH, VisionConfig, VisionError, ZoneConfigError,
)
from sentinel.vision.event_emitter import PhysicalEventEmitter
from sentinel.vision.pipeline import PerceptionPipeline
from sentinel.vision.tracker import UltralyticsByteTrackTracker
from sentinel.vision.zones import ZoneSet
from simulator.scenarios import procedure

WINDOW = "MADQAQ Sentinel - M1 Live Physical Perception"
REPO_ROOT = Path(__file__).resolve().parents[2]


def parse_args(argv: list[str] | None = None, prog: str = "python -m apps.vision_demo.main",
               description: str | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog=prog, description=description or __doc__.split("\n")[0])
    p.add_argument("--camera", type=int, default=0, help="webcam index (default 0)")
    p.add_argument("--model", default=DEFAULT_MODEL, help=f"Ultralytics person model (default {DEFAULT_MODEL})")
    p.add_argument("--zones", default=DEFAULT_ZONES_PATH, help=f"zone config JSON (default {DEFAULT_ZONES_PATH})")
    p.add_argument("--confidence", type=float, default=0.45, help="detector confidence threshold (default 0.45)")
    p.add_argument("--no-mirror", action="store_true", help="do not mirror the preview")
    p.add_argument("--debug-zones", action="store_true", help="show zone-stability diagnostics (raw/candidate/stable zone, dwell, smoothed point)")
    d = VisionConfig()
    p.add_argument("--zone-dwell-ms", type=float, default=d.zone_dwell_ms, help=f"ms a zone must be held before it is accepted (default {d.zone_dwell_ms:.0f})")
    p.add_argument("--smoothing-window", type=int, default=d.smoothing_window, help=f"ground-point median window in frames (default {d.smoothing_window})")
    p.add_argument("--boundary-margin", type=float, default=d.boundary_margin, help=f"normalized zone-boundary hysteresis margin (default {d.boundary_margin})")
    return p.parse_args(argv)


def resolve_zones_path(path: str) -> str:
    p = Path(path)
    if not p.is_file() and not p.is_absolute() and (REPO_ROOT / p).is_file():
        return str(REPO_ROOT / p)
    return path


def run(args: argparse.Namespace) -> int:
    cfg = VisionConfig(camera_index=args.camera, model=args.model, zones_path=args.zones,
                       confidence=args.confidence, mirror=not args.no_mirror, debug_zones=args.debug_zones,
                       zone_dwell_ms=args.zone_dwell_ms, smoothing_window=args.smoothing_window,
                       boundary_margin=args.boundary_margin)
    cfg.validate()
    zones = ZoneSet.load(resolve_zones_path(cfg.zones_path))
    proc = procedure()
    cv2 = import_cv2()
    import numpy as np

    print(f"Loading model {cfg.model} ...")
    tracker = UltralyticsByteTrackTracker.load(cfg.model, cfg.confidence)
    emitter = PhysicalEventEmitter(zones, proc.procedure_id, cfg)
    pipeline = PerceptionPipeline(zones, emitter, proc, ConformanceEngine(), tracker)

    from apps.vision_demo.overlay import draw_panel, draw_scene

    with Camera.open(cfg.camera_index) as cam:
        print("Camera open. Q/ESC quit, R reset.")
        try:
            cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
        except cv2.error as exc:
            raise VisionError("Cannot open a display window (is opencv-python-headless installed instead of opencv-python?): " + str(exc)) from exc
        notice = ""
        while True:
            frame = cam.read()
            if frame is None:
                continue  # transient read hiccup; Camera raises if it persists
            if cfg.mirror:
                frame = cv2.flip(frame, 1)
            result = pipeline.process_frame(frame)
            focus = pipeline.focus_journey_id()
            summary = pipeline.summarize(focus) if focus else None
            focus_tracker = pipeline.emitter.journeys[focus].tracker_id if focus else None
            draw_scene(cv2, frame, zones, result, cfg.debug_zones, focus_tracker)
            canvas = np.hstack([frame, draw_panel(cv2, np, frame.shape[0], summary, zones, notice)])
            cv2.imshow(WINDOW, canvas)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), ord("Q"), 27):
                break
            if key in (ord("r"), ord("R")):
                pipeline.reset()
                notice = "Reset: journeys and events cleared"
            elif result.new_events:
                notice = ""
            try:
                if cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                    break  # window closed with the X button
            except cv2.error:
                break
    cv2.destroyAllWindows()
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        return run(args)
    except KeyboardInterrupt:
        return 0
    except VisionError as exc:
        label = "Zone configuration error" if isinstance(exc, ZoneConfigError) else "Error"
        print(f"{label}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
