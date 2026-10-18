/**
 * Frontend configuration. Sampling values are starting points for a LOCAL demo, not tuned values.
 * NEXT_PUBLIC_* variables are referenced literally so Next.js can inline them at build time.
 */

function numberOr(raw: string | undefined, fallback: number, min: number, max: number): number {
  const n = raw === undefined || raw.trim() === "" ? NaN : Number(raw);
  return Number.isFinite(n) && n >= min && n <= max ? n : fallback;
}

export const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
export const WS_BASE_URL = (process.env.NEXT_PUBLIC_WS_URL || "ws://127.0.0.1:8000").replace(/\/$/, "");
export const WS_SESSION_PATH = "/ws/session";
export const HEALTH_PATH = "/web/health";

export const SAMPLING = {
  /** frames per second sent for analysis (the displayed video is NOT limited by this) */
  fps: numberOr(process.env.NEXT_PUBLIC_SAMPLE_FPS, 6, 1, 15),
  /** sampled frames are downscaled to at most this width before JPEG encoding */
  maxWidth: numberOr(process.env.NEXT_PUBLIC_MAX_ANALYSIS_WIDTH, 960, 160, 1920),
  jpegQuality: numberOr(process.env.NEXT_PUBLIC_JPEG_QUALITY, 0.75, 0.3, 0.95),
  /** mirror the preview AND the sampled frames, matching the M1 desktop demo (selfie view) */
  mirror: true,
} as const;

export const RECONNECT = { initialMs: 1000, maxMs: 8000 } as const;
/** a frame without a reply after this long no longer blocks the next one */
export const FRAME_REPLY_TIMEOUT_MS = 3000;
/** detections older than this are not drawn */
export const DETECTION_STALE_MS = 1500;
export const EVIDENCE_TIMEOUT_MS = 5000;
export const NOTICE_MS = 4500;
export const TIMELINE_ROWS = 10;
