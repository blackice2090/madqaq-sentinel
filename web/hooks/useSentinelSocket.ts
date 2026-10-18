"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { EVIDENCE_TIMEOUT_MS, FRAME_REPLY_TIMEOUT_MS, RECONNECT, WS_BASE_URL, WS_SESSION_PATH } from "@/lib/config";
import { nextBackoff, type ConnectionStatus } from "@/lib/connection";
import {
  encodeCommand, parseServerMessage, type ClientCommand, type HelloMessage, type SessionState,
} from "@/lib/protocol";

export interface Notice { id: number; tone: "info" | "warn"; text: string }

interface Waiter { resolve: (e: Record<string, unknown>) => void; reject: (err: Error) => void; timer: number }

/** One WebSocket = one isolated backend session. A reconnect starts a NEW session (new journey). */
export function useSentinelSocket(url: string = WS_BASE_URL + WS_SESSION_PATH) {
  const [connection, setConnection] = useState<ConnectionStatus>("connecting");
  const [state, setState] = useState<SessionState | null>(null);
  const [hello, setHello] = useState<HelloMessage | null>(null);
  const [lastStateAt, setLastStateAt] = useState<number | null>(null);
  const [notice, setNotice] = useState<Notice | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const frameSentAt = useRef<number | null>(null);
  const waiter = useRef<Waiter | null>(null);
  const noticeId = useRef(0);

  const pushNotice = useCallback((tone: Notice["tone"], text: string) => {
    noticeId.current += 1;
    setNotice({ id: noticeId.current, tone, text });
  }, []);

  useEffect(() => {
    let disposed = false;
    let retryMs: number = RECONNECT.initialMs;
    let timer: number | undefined;

    const failWaiter = (msg: string) => {
      const w = waiter.current;
      if (w) { window.clearTimeout(w.timer); waiter.current = null; w.reject(new Error(msg)); }
    };

    const open = () => {
      const ws = new WebSocket(url);
      ws.binaryType = "arraybuffer";
      wsRef.current = ws;
      ws.onopen = () => {
        if (disposed) return;
        retryMs = RECONNECT.initialMs;
        setConnection("connected");
      };
      ws.onmessage = (ev: MessageEvent) => {
        if (disposed || typeof ev.data !== "string") return;
        const msg = parseServerMessage(ev.data);
        if (!msg) return;
        switch (msg.type) {
          case "hello":
            setHello(msg);
            break;
          case "state":
            frameSentAt.current = null;
            setState(msg);
            setLastStateAt(Date.now());
            if (msg.notice) pushNotice("warn", msg.notice);
            break;
          case "ack":
            pushNotice(msg.ok ? "info" : "warn", msg.message);
            break;
          case "error":
            if (msg.code === "no_journey" && waiter.current) failWaiter(msg.message);
            else pushNotice("warn", msg.message);
            break;
          case "evidence": {
            const w = waiter.current;
            if (w) { window.clearTimeout(w.timer); waiter.current = null; w.resolve(msg.evidence); }
            break;
          }
          default:
            break;
        }
      };
      ws.onclose = () => {
        if (wsRef.current === ws) wsRef.current = null;
        frameSentAt.current = null;
        failWaiter("Backend disconnected.");
        if (disposed) return;
        setConnection("disconnected");
        timer = window.setTimeout(() => {
          if (disposed) return;
          setConnection("connecting");
          open();
        }, retryMs);
        retryMs = nextBackoff(retryMs, RECONNECT.maxMs);
      };
    };

    open();
    return () => {
      disposed = true;
      if (timer !== undefined) window.clearTimeout(timer);
      failWaiter("Closed.");
      const ws = wsRef.current;
      wsRef.current = null;
      ws?.close();
    };
  }, [url, pushNotice]);

  /** Sends one JPEG frame unless the previous frame is still awaiting its reply. */
  const sendFrame = useCallback((jpeg: ArrayBuffer): boolean => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return false;
    const now = Date.now();
    if (frameSentAt.current !== null && now - frameSentAt.current < FRAME_REPLY_TIMEOUT_MS) return false;
    frameSentAt.current = now;
    ws.send(jpeg);
    return true;
  }, []);

  const canSendFrame = useCallback((): boolean => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return false;
    return frameSentAt.current === null || Date.now() - frameSentAt.current >= FRAME_REPLY_TIMEOUT_MS;
  }, []);

  const sendCommand = useCallback((command: ClientCommand): boolean => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return false;
    ws.send(encodeCommand(command));
    return true;
  }, []);

  const requestEvidence = useCallback((): Promise<Record<string, unknown>> => {
    return new Promise((resolve, reject) => {
      const ws = wsRef.current;
      if (!ws || ws.readyState !== WebSocket.OPEN) { reject(new Error("Backend not connected.")); return; }
      if (waiter.current) { reject(new Error("An evidence request is already pending.")); return; }
      const timer = window.setTimeout(() => {
        waiter.current = null;
        reject(new Error("Evidence request timed out."));
      }, EVIDENCE_TIMEOUT_MS);
      waiter.current = { resolve, reject, timer };
      ws.send(encodeCommand("get_evidence"));
    });
  }, []);

  return { connection, state, hello, lastStateAt, notice, sendFrame, canSendFrame, sendCommand, requestEvidence, pushNotice };
}
