/**
 * Overlay geometry. Zones and boxes arrive NORMALIZED (0..1) relative to the analysed frame, which has the
 * same aspect ratio and orientation as the displayed (mirrored) preview. They are mapped onto the actual
 * drawn video rectangle (object-fit: contain), so resizing never misplaces them.
 */
import type { Box, Detection, Zone } from "./protocol";

export interface Rect { x: number; y: number; w: number; h: number }

export function containRect(containerW: number, containerH: number, mediaW: number, mediaH: number): Rect {
  if (containerW <= 0 || containerH <= 0 || mediaW <= 0 || mediaH <= 0) return { x: 0, y: 0, w: 0, h: 0 };
  const scale = Math.min(containerW / mediaW, containerH / mediaH);
  const w = mediaW * scale;
  const h = mediaH * scale;
  return { x: (containerW - w) / 2, y: (containerH - h) / 2, w, h };
}

export function mapBox(box: Box, rect: Rect): Rect {
  const [x1, y1, x2, y2] = box;
  return { x: rect.x + x1 * rect.w, y: rect.y + y1 * rect.h, w: (x2 - x1) * rect.w, h: (y2 - y1) * rect.h };
}

export function zoneBox(z: Zone): Box {
  return [z.x1, z.y1, z.x2, z.y2];
}

/** Downscaled analysis size, preserving aspect ratio. */
export function analysisSize(videoW: number, videoH: number, maxWidth: number): { width: number; height: number } {
  if (videoW <= 0 || videoH <= 0) return { width: 0, height: 0 };
  const scale = Math.min(1, maxWidth / videoW);
  return { width: Math.max(1, Math.round(videoW * scale)), height: Math.max(1, Math.round(videoH * scale)) };
}

const C = { cream: "#F5F1E8", ember: "#D9784A", ink: "#18312F" };

export interface OverlayInput {
  zones: Zone[];
  activeZone: string | null;
  detections: Detection[];
  showDetections: boolean;
}

/** Draws in CSS pixels; the caller sets the device-pixel-ratio transform. */
export function drawOverlay(ctx: CanvasRenderingContext2D, rect: Rect, input: OverlayInput): void {
  const font = Math.max(15, Math.round(rect.h / 22));
  ctx.lineJoin = "round";
  for (const z of input.zones) {
    const r = mapBox(zoneBox(z), rect);
    const active = z.zone_id === input.activeZone;
    ctx.fillStyle = active ? "rgba(217,120,74,0.22)" : "rgba(245,241,232,0.05)";
    ctx.fillRect(r.x, r.y, r.w, r.h);
    ctx.setLineDash(active ? [] : [10, 7]);
    ctx.lineWidth = active ? 5 : 2;
    ctx.strokeStyle = active ? C.ember : "rgba(245,241,232,0.6)";
    ctx.strokeRect(r.x, r.y, r.w, r.h);
    ctx.setLineDash([]);
    const label = `${z.zone_id}  ${z.name}`;
    ctx.font = `700 ${font}px ui-sans-serif, system-ui, sans-serif`;
    const pad = font * 0.5;
    const bw = Math.min(ctx.measureText(label).width + pad * 2, r.w - 8);
    ctx.fillStyle = active ? C.ember : "rgba(8,45,43,0.82)";
    ctx.fillRect(r.x + 4, r.y + 4, bw, font + pad * 1.4);
    ctx.fillStyle = active ? C.ink : C.cream;
    ctx.textBaseline = "top";
    ctx.fillText(label, r.x + 4 + pad, r.y + 4 + pad * 0.7, bw - pad * 2);
  }
  if (!input.showDetections) return;
  // The person box is deliberately thin and unlabelled; ID / zone / confidence live in the panel's status chip.
  for (const d of input.detections) {
    const r = mapBox(d.box, rect);
    ctx.lineWidth = 2;
    ctx.strokeStyle = d.in_active_journey ? "rgba(245,241,232,0.95)" : "rgba(245,241,232,0.5)";
    ctx.strokeRect(r.x, r.y, r.w, r.h);
  }
}
