/** Browser camera helpers (getUserMedia error mapping). */

export type PermissionView = "unknown" | "prompt" | "granted" | "denied" | "unsupported";

export function cameraErrorMessage(err: unknown): string {
  const name = typeof err === "object" && err !== null && "name" in err ? String((err as { name: unknown }).name) : "";
  switch (name) {
    case "NotAllowedError":
    case "SecurityError":
      return "Camera permission was denied. Allow camera access for this site in the browser, then press Start Camera.";
    case "NotFoundError":
    case "OverconstrainedError":
      return "No suitable camera was found. Connect a webcam and try again.";
    case "NotReadableError":
    case "AbortError":
      return "The camera is in use by another application or could not be started.";
    case "UnsupportedError":
      return "This browser does not allow camera access here. Open the dashboard at http://localhost:3000.";
    default:
      return "The camera could not be started.";
  }
}

export function cameraSupported(): boolean {
  return typeof navigator !== "undefined" && !!navigator.mediaDevices?.getUserMedia;
}
