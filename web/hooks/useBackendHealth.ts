"use client";

import { useEffect, useState } from "react";

import { API_BASE_URL, HEALTH_PATH } from "@/lib/config";

export interface BackendHealth { ok: boolean; engineVersion: string | null; websocketSupport: boolean | null; checkedAt: number }

/** Polls GET /web/health so the header can show backend health independently of the socket. */
export function useBackendHealth(periodMs = 10_000): BackendHealth | null {
  const [health, setHealth] = useState<BackendHealth | null>(null);
  useEffect(() => {
    let cancelled = false;
    const check = () => {
      fetch(API_BASE_URL + HEALTH_PATH, { cache: "no-store" })
        .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
        .then((body: { status?: unknown; engine_version?: unknown; websocket_support?: unknown }) => {
          if (!cancelled) setHealth({
            ok: body.status === "ok",
            engineVersion: typeof body.engine_version === "string" ? body.engine_version : null,
            websocketSupport: typeof body.websocket_support === "boolean" ? body.websocket_support : null,
            checkedAt: Date.now(),
          });
        })
        .catch(() => { if (!cancelled) setHealth({ ok: false, engineVersion: null, websocketSupport: null, checkedAt: Date.now() }); });
    };
    check();
    const t = window.setInterval(check, periodMs);
    return () => { cancelled = true; window.clearInterval(t); };
  }, [periodMs]);
  return health;
}
