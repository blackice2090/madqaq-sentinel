"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { cameraErrorMessage, cameraSupported, type PermissionView } from "@/lib/camera";
import type { CameraStatus } from "@/lib/connection";

/** Browser-owned webcam. Nothing starts (and nothing is uploaded) until the user presses Start Camera. */
export function useCamera() {
  const [status, setStatus] = useState<CameraStatus>("off");
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [permission, setPermission] = useState<PermissionView>("unknown");
  const streamRef = useRef<MediaStream | null>(null);

  useEffect(() => {
    let status: PermissionStatus | null = null;
    let cancelled = false;
    const perms = typeof navigator !== "undefined" ? navigator.permissions : undefined;
    if (!cameraSupported()) {
      queueMicrotask(() => { if (!cancelled) setPermission("unsupported"); });
      return () => { cancelled = true; };
    }
    perms?.query({ name: "camera" as PermissionName }).then((s) => {
      if (cancelled) return;
      status = s;
      setPermission(s.state as PermissionView);
      s.onchange = () => setPermission(s.state as PermissionView);
    }).catch(() => { /* Permissions API not available for camera in this browser */ });
    return () => {
      cancelled = true;
      if (status) status.onchange = null;
    };
  }, []);

  const stop = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    setStream(null);
    setStatus("off");
  }, []);

  const start = useCallback(async () => {
    setError(null);
    if (!cameraSupported()) {
      setStatus("error");
      setPermission("unsupported");
      setError(cameraErrorMessage({ name: "UnsupportedError" }));
      return;
    }
    setStatus("starting");
    try {
      const s = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: "user" },
        audio: false,
      });
      streamRef.current?.getTracks().forEach((t) => t.stop());
      streamRef.current = s;
      s.getVideoTracks().forEach((t) => { t.onended = () => stop(); });
      setStream(s);
      setStatus("active");
      setPermission("granted");
    } catch (err) {
      setStatus("error");
      setError(cameraErrorMessage(err));
      if (typeof err === "object" && err && "name" in err && (err as { name: string }).name === "NotAllowedError") {
        setPermission("denied");
      }
    }
  }, [stop]);

  useEffect(() => () => { streamRef.current?.getTracks().forEach((t) => t.stop()); }, []);

  return { status, stream, error, permission, start, stop };
}
