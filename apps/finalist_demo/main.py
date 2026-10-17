"""M3 finalist demo: live camera + SIMULATED digital channel, presented as a procedure-integrity dashboard.

    python -m apps.finalist_demo.main --confidence 0.50 [--debug-zones] [--canvas 1600x900]
                                      [--evidence-dir artifacts/evidence]

Keys: 1 digital full trace | 2 digital without B | 3 digital B failed | 0 clear digital
      S save evidence snapshot (PNG + JSON) | R reset | Q / ESC quit

The digital channel is a LOCAL SIMULATOR. It is not connected to any real checkpoint system.
"""
from __future__ import annotations

import sys
import time

from apps.dual_channel_demo.main import NOTICE_SECONDS, handle_key
from apps.vision_demo.main import parse_args, resolve_zones_path
from sentinel.conformance.engine import ConformanceEngine
from sentinel.dual_channel import DualChannelCoordinator, DualChannelError
from sentinel.presentation import build_dashboard_model, save_snapshot
from sentinel.presentation.evidence import DEFAULT_DIR
from sentinel.vision.camera import Camera, import_cv2
from sentinel.vision.config import VisionConfig, VisionError, ZoneConfigError
from sentinel.vision.event_emitter import PhysicalEventEmitter
from sentinel.vision.pipeline import PerceptionPipeline
from sentinel.vision.tracker import UltralyticsByteTrackTracker
from sentinel.vision.zones import ZoneSet
from simulator.scenarios import procedure

WINDOW = "MADQAQ Sentinel - Procedure Integrity Monitor (digital channel is SIMULATED)"
MIN_CANVAS = (960, 540)


def _configure(p) -> None:
    p.add_argument("--canvas", default="1600x900", help="dashboard size WIDTHxHEIGHT (default 1600x900; try 1920x1080)")
    p.add_argument("--evidence-dir", default=DEFAULT_DIR, help=f"where S saves PNG+JSON (default {DEFAULT_DIR})")


def parse_canvas(text: str) -> tuple[int, int]:
    try:
        w, h = (int(v) for v in text.lower().split("x"))
    except ValueError:
        raise VisionError(f"Invalid --canvas '{text}': use WIDTHxHEIGHT, for example 1600x900.") from None
    if w < MIN_CANVAS[0] or h < MIN_CANVAS[1]:
        raise VisionError(f"--canvas {w}x{h} is too small; the minimum is {MIN_CANVAS[0]}x{MIN_CANVAS[1]}.")
    return w, h


def run(args) -> int:
    cfg = VisionConfig(camera_index=args.camera, model=args.model, zones_path=args.zones,
                       confidence=args.confidence, mirror=not args.no_mirror, debug_zones=args.debug_zones,
                       zone_dwell_ms=args.zone_dwell_ms, smoothing_window=args.smoothing_window,
                       boundary_margin=args.boundary_margin)
    cfg.validate()
    W, H = parse_canvas(args.canvas)
    zones = ZoneSet.load(resolve_zones_path(cfg.zones_path))
    proc = procedure()
    cv2 = import_cv2()
    try:
        from apps.finalist_demo.fonts import FontKit
        from apps.finalist_demo.render import layout_dashboard, paint, to_bgr
    except ImportError as exc:
        raise VisionError('Pillow is required for the finalist dashboard. Run:  pip install -e ".[vision]"') from exc
    kit = FontKit()

    print(f"Loading model {cfg.model} ...")
    tracker = UltralyticsByteTrackTracker.load(cfg.model, cfg.confidence)
    engine = ConformanceEngine()
    emitter = PhysicalEventEmitter(zones, proc.procedure_id, cfg)
    pipeline = PerceptionPipeline(zones, emitter, proc, engine, tracker)   # M1, unchanged
    coordinator = DualChannelCoordinator(proc, engine)                      # M2, unchanged

    with Camera.open(cfg.camera_index) as cam:
        print("Camera open. 1/2/3 simulated digital, 0 clear, S save evidence, R reset, Q/ESC quit.")
        try:
            cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(WINDOW, W, H)
        except cv2.error as exc:
            raise VisionError("Cannot open a display window (is opencv-python-headless installed instead of opencv-python?): " + str(exc)) from exc
        notice, notice_until = "", 0.0
        layout, last_key = None, None   # re-layout only when the displayed content changes
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
            if time.monotonic() > notice_until:
                notice = ""

            model = build_dashboard_model(coordinator, result.persons, debug=cfg.debug_zones)
            if layout is None or (model, notice) != last_key:
                layout, last_key = layout_dashboard(model, W, H, kit, notice), (model, notice)
            image = paint(layout, kit, frame, zones, result.persons, cfg.debug_zones)
            cv2.imshow(WINDOW, to_bgr(image))

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), ord("Q"), 27):
                break
            msg = None
            if key in (ord("s"), ord("S")):
                try:
                    paths = save_snapshot(coordinator, lambda p: (image.save(p), True)[1], args.evidence_dir)
                    msg = f"Saved evidence: {paths.png.name} (+ .json) in {args.evidence_dir}"
                except (DualChannelError, OSError) as exc:
                    msg = str(exc)
            elif key != 255:
                msg = handle_key(key, coordinator, pipeline)
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
    args = parse_args(argv, prog="python -m apps.finalist_demo.main",
                      description="M3 finalist demo: procedure-integrity dashboard (digital channel SIMULATED)",
                      configure=_configure)
    try:
        return run(args)
    except KeyboardInterrupt:
        return 0
    except (VisionError, DualChannelError) as exc:
        label = "Zone configuration error" if isinstance(exc, ZoneConfigError) else "Error"
        print(f"{label}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
