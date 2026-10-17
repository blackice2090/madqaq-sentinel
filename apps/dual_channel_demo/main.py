"""M2 dual-channel live demo: live camera (PHYSICAL) + SIMULATED digital channel -> M0 engine.

    python -m apps.dual_channel_demo.main [--camera 0] [--model yolo11n.pt]
                                          [--zones config/checkpoint_zones.json] [--confidence 0.50]
                                          [--debug-zones]

Keys: 1 inject full digital trace | 2 digital trace without B | 3 digital trace with B failed
      0 clear digital evidence    | R reset everything         | Q / ESC quit

The digital channel is a LOCAL SIMULATOR. It is not connected to any real checkpoint system.
"""
from __future__ import annotations

import sys
import time

from apps.vision_demo.main import parse_args, resolve_zones_path
from sentinel.conformance.engine import ConformanceEngine
from sentinel.digital.presets import PRESETS_BY_KEY
from sentinel.dual_channel import DualChannelCoordinator, DualChannelError
from sentinel.vision.camera import Camera, import_cv2
from sentinel.vision.config import VisionConfig, VisionError, ZoneConfigError
from sentinel.vision.event_emitter import PhysicalEventEmitter
from sentinel.vision.pipeline import PerceptionPipeline
from sentinel.vision.tracker import UltralyticsByteTrackTracker
from sentinel.vision.zones import ZoneSet
from simulator.scenarios import procedure

WINDOW = "MADQAQ Sentinel - M2 Dual-Channel (digital channel is SIMULATED)"
NOTICE_SECONDS = 6.0


def handle_key(key: int, coordinator: DualChannelCoordinator, pipeline: PerceptionPipeline) -> str | None:
    """Apply a digital-control key. Returns a notice for the operator (or None). Never raises for demo errors."""
    ch = chr(key) if 0 <= key < 256 else ""
    try:
        if ch in PRESETS_BY_KEY:
            preset = PRESETS_BY_KEY[ch]
            coordinator.inject_digital_preset(preset)
            return f"SIMULATED digital injected: {preset.title}"
        if ch == "0":
            coordinator.clear_digital()
            return "Simulated digital evidence cleared for the current journey."
        if ch in ("r", "R"):
            pipeline.reset()
            coordinator.reset()
            return "Reset: physical journey, digital evidence and verdict cleared."
    except DualChannelError as exc:
        return str(exc)
    return None


def run(args) -> int:
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
    engine = ConformanceEngine()
    emitter = PhysicalEventEmitter(zones, proc.procedure_id, cfg)
    pipeline = PerceptionPipeline(zones, emitter, proc, engine, tracker)   # M1, reused unchanged
    coordinator = DualChannelCoordinator(proc, engine)                      # M2 layer

    from apps.dual_channel_demo.overlay import MIN_HEIGHT, draw_dual_panel
    from apps.vision_demo.overlay import draw_scene

    with Camera.open(cfg.camera_index) as cam:
        print("Camera open. 1/2/3 simulated digital presets, 0 clear digital, R reset, Q/ESC quit.")
        try:
            cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
        except cv2.error as exc:
            raise VisionError("Cannot open a display window (is opencv-python-headless installed instead of opencv-python?): " + str(exc)) from exc
        notice, notice_until = "", 0.0
        while True:
            frame = cam.read()
            if frame is None:
                continue
            if cfg.mirror:
                frame = cv2.flip(frame, 1)
            result = pipeline.process_frame(frame)
            if result.new_events:
                try:
                    coordinator.add_physical_events(result.new_events)
                except DualChannelError as exc:
                    notice, notice_until = str(exc), time.monotonic() + NOTICE_SECONDS

            active = coordinator.active_journey_id
            rec = pipeline.emitter.journeys.get(active) if active else None
            draw_scene(cv2, frame, zones, result, cfg.debug_zones, rec.tracker_id if rec else None,
                       subtitle="Dual-Channel Integration - M2")
            summary = coordinator.summary() if active else None
            if time.monotonic() > notice_until:
                notice = ""
            panel, _ = draw_dual_panel(cv2, np, frame.shape[0], summary, notice)
            if frame.shape[0] < panel.shape[0]:  # pad the video area so both halves have equal height
                pad = np.zeros((panel.shape[0] - frame.shape[0], frame.shape[1], 3), dtype=np.uint8)
                frame = np.vstack([frame, pad])
            cv2.imshow(WINDOW, np.hstack([frame, panel]))

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), ord("Q"), 27):
                break
            msg = handle_key(key, coordinator, pipeline) if key != 255 else None
            if msg:
                notice, notice_until = msg, time.monotonic() + NOTICE_SECONDS
            try:
                if cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                    break
            except cv2.error:
                break
    cv2.destroyAllWindows()
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv, prog="python -m apps.dual_channel_demo.main",
                      description="M2 dual-channel demo: live camera + SIMULATED digital channel")
    try:
        return run(args)
    except KeyboardInterrupt:
        return 0
    except VisionError as exc:
        label = "Zone configuration error" if isinstance(exc, ZoneConfigError) else "Error"
        print(f"{label}: {exc}", file=sys.stderr)
        return 2
    except DualChannelError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
