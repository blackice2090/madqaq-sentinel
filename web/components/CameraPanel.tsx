"use client";

import { Camera, CameraOff, LoaderCircle, TriangleAlert } from "lucide-react";
import { useEffect, useRef, useState, type RefObject } from "react";

import type { PermissionView } from "@/lib/camera";
import { SAMPLING } from "@/lib/config";
import type { CameraStatus } from "@/lib/connection";
import { containRect, drawOverlay } from "@/lib/overlay";
import type { Detection, Zone } from "@/lib/protocol";

interface Props {
  videoRef: RefObject<HTMLVideoElement | null>;
  stream: MediaStream | null;
  cameraStatus: CameraStatus;
  cameraError: string | null;
  permission: PermissionView;
  onStart: () => void;
  onStop: () => void;
  zones: Zone[];
  activeZone: string | null;
  detections: Detection[];
  showDetections: boolean;
  trackingLine: string;
}

export function CameraPanel(p: Props) {
  const boxRef = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [box, setBox] = useState({ w: 0, h: 0 });
  const [media, setMedia] = useState({ w: 0, h: 0 });
  const { videoRef, stream } = p;

  // Attach the LOCAL MediaStream to the video element (the displayed video never goes through the backend).
  useEffect(() => {
    const v = videoRef.current;
    if (!v) return;
    v.srcObject = stream;
    if (stream) v.play().catch(() => { /* autoplay is muted; ignore */ });
  }, [stream, videoRef]);

  useEffect(() => {
    const el = boxRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => {
      if (entry) setBox({ w: entry.contentRect.width, h: entry.contentRect.height });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    const v = videoRef.current;
    if (!v) return;
    const update = () => setMedia({ w: v.videoWidth, h: v.videoHeight });
    v.addEventListener("loadedmetadata", update);
    v.addEventListener("resize", update);
    return () => { v.removeEventListener("loadedmetadata", update); v.removeEventListener("resize", update); };
  }, [videoRef]);

  const active = p.cameraStatus === "active";

  useEffect(() => {
    const c = canvasRef.current;
    if (!c) return;
    const dpr = window.devicePixelRatio || 1;
    c.width = Math.round(box.w * dpr);
    c.height = Math.round(box.h * dpr);
    const ctx = c.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, box.w, box.h);
    if (!active || media.w === 0) return;
    const rect = containRect(box.w, box.h, media.w, media.h);
    drawOverlay(ctx, rect, {
      zones: p.zones, activeZone: p.showDetections ? p.activeZone : null,
      detections: p.detections, showDetections: p.showDetections,
    });
  }, [box, media, active, p.zones, p.activeZone, p.detections, p.showDetections]);

  return (
    <section aria-label="Live camera" className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl bg-forest-deep">
      <header className="flex items-center justify-between gap-3 px-4 py-2 text-cream">
        <h2 className="text-xs font-semibold uppercase tracking-[0.16em] text-cream/80">Live camera</h2>
        <div className="flex items-center gap-2">
          {active ? (
            <button type="button" onClick={p.onStop}
              className="inline-flex items-center gap-2 rounded-lg border border-cream/40 px-3 py-1.5 text-sm font-bold text-cream hover:bg-white/10 focus-visible:outline-2 focus-visible:outline-ember">
              <CameraOff aria-hidden className="size-4" /> Stop Camera
            </button>
          ) : (
            <button type="button" onClick={p.onStart} disabled={p.cameraStatus === "starting"}
              className="inline-flex items-center gap-2 rounded-lg bg-ember px-3 py-1.5 text-sm font-bold text-ink hover:brightness-105 disabled:opacity-60 focus-visible:outline-2 focus-visible:outline-cream">
              {p.cameraStatus === "starting" ? <LoaderCircle aria-hidden className="size-4 animate-spin" /> : <Camera aria-hidden className="size-4" />}
              Start Camera
            </button>
          )}
        </div>
      </header>
      <div ref={boxRef} className="relative min-h-[140px] w-full flex-1 overflow-hidden bg-black">
        <video ref={videoRef} muted playsInline autoPlay
          className={`absolute inset-0 h-full w-full object-contain ${SAMPLING.mirror ? "-scale-x-100" : ""} ${active ? "" : "invisible"}`} />
        <canvas ref={canvasRef} className="pointer-events-none absolute inset-0 h-full w-full" aria-hidden />
        {active && (
          <span className="absolute bottom-3 left-3 rounded-md bg-forest-deep/80 px-2.5 py-1 text-sm font-semibold text-cream">
            {p.trackingLine}
          </span>
        )}
        {!active && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 p-6 text-center text-cream">
            {p.cameraStatus === "error" ? <TriangleAlert aria-hidden className="size-10 text-ember" /> : <CameraOff aria-hidden className="size-10 text-cream/60" />}
            <p className="text-xl font-bold">{p.cameraStatus === "error" ? "Camera unavailable" : "CAMERA OFF"}</p>
            <p className="max-w-lg text-sm text-cream/80">
              {p.cameraError ?? "Press Start Camera to begin. No frames are sent to the backend until the camera is started."}
            </p>
            {p.permission === "denied" && (
              <p className="text-xs text-cream/70">Permission is blocked: use the camera icon in the browser address bar to allow it.</p>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
