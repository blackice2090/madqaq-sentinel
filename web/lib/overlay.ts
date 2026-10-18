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

const C = { forest: "#0E3F3C", cream: "#F7F1E7", ember: "#D9784A", ink: "#0B1F1E" };

export interface OverlayInput {
  zones: Zone[];
  activeZone: string | null;
  detections: Detection[];
  showDetections: boolean;
}

/** Draws in CSS pixels; the caller sets the device-pixel-ratio transform. */
export function drawOverlay(ctx: CanvasRenderingContext2D, rect: Rect, input: OverlayInput): void {
  const font = Math.max(12, Math.round(rect.h / 30));
  ctx.lineJoin = "round";
  for (const z of input.zones) {
    const r = mapBox(zoneBox(z), rect);
    const active = z.zone_id === input.activeZone;
    ctx.fillStyle = active ? "rgba(217,120,74,0.20)" : "rgba(14,63,60,0.14)";
    ctx.fillRect(r.x, r.y, r.w, r.h);
    ctx.setLineDash(active ? [] : [8, 6]);
    ctx.lineWidth = active ? 4 : 2;
    ctx.strokeStyle = active ? C.ember : "rgba(247,241,231,0.85)";
    ctx.strokeRect(r.x, r.y, r.w, r.h);
    ctx.setLineDash([]);
    const label = active ? `${z.zone_id} ${z.name} · ACTIVE` : `${z.zone_id} ${z.name}`;
    ctx.font = `600 ${font}px ui-sans-serif, system-ui, sans-serif`;
    const tw = ctx.measureText(label).width;
    const pad = font * 0.4;
    ctx.fillStyle = active ? C.ember : "rgba(14,63,60,0.88)";
    ctx.fillRect(r.x + 4, r.y + 4, Math.min(tw + pad * 2, r.w - 8), font + pad * 1.4);
    ctx.fillStyle = active ? C.ink : C.cream;
    ctx.textBaseline = "top";
    ctx.fillText(label, r.x + 4 + pad, r.y + 4 + pad * 0.7, r.w - 8 - pad * 2);
  }
  if (!input.showDetections) return;
  for (const d of input.detections) {
    const r = mapBox(d.box, rect);
    ctx.lineWidth = 3;
    ctx.strokeStyle = d.in_active_journey ? C.ember : C.cream;
    ctx.strokeRect(r.x, r.y, r.w, r.h);
    const label = `ID ${d.tracker_id} · ${d.zone_id ? `Zone ${d.zone_id}` : "outside zones"} · ${d.confidence.toFixed(2)}`;
    ctx.font = `600 ${font}px ui-sans-serif, system-ui, sans-serif`;
    const tw = ctx.measureText(label).width;
    const y = Math.max(rect.y, r.y - font - 10);
    ctx.fillStyle = "rgba(11,31,30,0.85)";
    ctx.fillRect(r.x, y, tw + 12, font + 8);
    ctx.fillStyle = C.cream;
    ctx.textBaseline = "top";
    ctx.fillText(label, r.x + 6, y + 4);
  }
}
