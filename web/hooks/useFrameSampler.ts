"use client";

import { useEffect, useRef, type RefObject } from "react";

import { SAMPLING } from "@/lib/config";
import { analysisSize } from "@/lib/overlay";

interface Options {
  videoRef: RefObject<HTMLVideoElement | null>;
  /** only true while the camera is active AND the backend is connected */
  enabled: boolean;
  canSend: () => boolean;
  send: (jpeg: ArrayBuffer) => boolean;
}

/**
 * Samples the LOCAL video at SAMPLING.fps into downscaled JPEGs and sends them for analysis.
 * The on-screen video is never routed through the backend. At most one frame is in flight.
 */
export function useFrameSampler({ videoRef, enabled, canSend, send }: Options): void {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const encoding = useRef(false);

  useEffect(() => {
    if (!enabled) return;
    const interval = window.setInterval(() => {
      const video = videoRef.current;
      if (!video || video.readyState < 2 || encoding.current || !canSend()) return;
      const { width, height } = analysisSize(video.videoWidth, video.videoHeight, SAMPLING.maxWidth);
      if (width === 0) return;
      if (!canvasRef.current) canvasRef.current = document.createElement("canvas");
      const canvas = canvasRef.current;
      if (canvas.width !== width) canvas.width = width;
      if (canvas.height !== height) canvas.height = height;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      ctx.save();
      if (SAMPLING.mirror) { ctx.translate(width, 0); ctx.scale(-1, 1); }
      ctx.drawImage(video, 0, 0, width, height);
      ctx.restore();
      encoding.current = true;
      canvas.toBlob((blob) => {
        if (!blob) { encoding.current = false; return; }
        blob.arrayBuffer().then((buf) => { send(buf); }).finally(() => { encoding.current = false; });
      }, "image/jpeg", SAMPLING.jpegQuality);
    }, Math.round(1000 / SAMPLING.fps));
    return () => window.clearInterval(interval);
  }, [enabled, videoRef, canSend, send]);
}
