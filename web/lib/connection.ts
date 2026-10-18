/** Connection / staleness rules: never present results as live when the backend is not connected. */
import type { SessionState } from "./protocol";

export type ConnectionStatus = "connecting" | "connected" | "disconnected";
export type CameraStatus = "off" | "starting" | "active" | "error";

export interface StatusView {
  backendLabel: "BACKEND CONNECTED" | "CONNECTING" | "DISCONNECTED";
  cameraLabel: "CAMERA ACTIVE" | "CAMERA OFF";
  /** results must be shown as stale / unavailable */
  stale: boolean;
  staleReason: string | null;
}

export function statusView(connection: ConnectionStatus, camera: CameraStatus, state: SessionState | null): StatusView {
  const backendLabel = connection === "connected" ? "BACKEND CONNECTED"
    : connection === "connecting" ? "CONNECTING" : "DISCONNECTED";
  const cameraLabel = camera === "active" ? "CAMERA ACTIVE" : "CAMERA OFF";
  let staleReason: string | null = null;
  if (connection !== "connected") {
    staleReason = connection === "connecting"
      ? "Connecting to the local analysis backend — results unavailable."
      : "Backend disconnected — results are stale and unavailable.";
  } else if (state === null) {
    staleReason = "Waiting for the first session state.";
  }
  return { backendLabel, cameraLabel, stale: staleReason !== null, staleReason };
}

/** Detections are drawn only while live and recent. */
export function detectionsFresh(connection: ConnectionStatus, camera: CameraStatus, lastStateAt: number | null,
                                now: number, maxAgeMs: number): boolean {
  return connection === "connected" && camera === "active" && lastStateAt !== null && now - lastStateAt <= maxAgeMs;
}

export function nextBackoff(currentMs: number, maxMs: number): number {
  return Math.min(maxMs, Math.max(1, currentMs) * 2);
}
