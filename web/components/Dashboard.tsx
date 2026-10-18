"use client";

import { Info, TriangleAlert } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useBackendHealth } from "@/hooks/useBackendHealth";
import { useCamera } from "@/hooks/useCamera";
import { useFrameSampler } from "@/hooks/useFrameSampler";
import { useNow } from "@/hooks/useNow";
import { useSentinelSocket } from "@/hooks/useSentinelSocket";
import { DETECTION_STALE_MS, NOTICE_MS } from "@/lib/config";
import { detectionsFresh, statusView } from "@/lib/connection";
import { DEFAULT_DISCLOSURES } from "@/lib/disclosures";
import { downloadJson, evidenceFilename } from "@/lib/evidence";
import { analysisStatus, DEFAULT_MODE, MODE_STORAGE_KEY, parseMode, type UiMode } from "@/lib/presentation";
import type { ClientCommand } from "@/lib/protocol";

import { AppHeader } from "./AppHeader";
import { CameraPanel } from "./CameraPanel";
import { DemoControlsDrawer } from "./DemoControlsDrawer";
import { EvidenceTimeline } from "./EvidenceTimeline";
import { EvidenceTracks } from "./EvidenceTracks";
import { PrivacyFooter } from "./PrivacyFooter";
import { StepStateList } from "./StepStateList";
import { VerdictCard } from "./VerdictCard";

const FALLBACK_EXPECTED = [
  { step_id: "A", name: "Entry" }, { step_id: "B", name: "Credential Check" },
  { step_id: "C", name: "Screening" }, { step_id: "D", name: "Exit" },
];

export function Dashboard() {
  const socket = useSentinelSocket();
  const camera = useCamera();
  const health = useBackendHealth();
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const now = useNow(500);
  const [saving, setSaving] = useState(false);
  const [mode, setMode] = useState<UiMode>(DEFAULT_MODE);
  useEffect(() => {
    let saved: UiMode = DEFAULT_MODE;
    try { saved = parseMode(window.localStorage.getItem(MODE_STORAGE_KEY)); } catch { /* storage unavailable */ }
    if (saved === DEFAULT_MODE) return;
    const t = window.setTimeout(() => setMode(saved), 0);
    return () => window.clearTimeout(t);
  }, []);
  const changeMode = useCallback((m: UiMode) => {
    setMode(m);
    try { window.localStorage.setItem(MODE_STORAGE_KEY, m); } catch { /* storage unavailable */ }
  }, []);
  const [visibleNotice, setVisibleNotice] = useState<{ id: number; tone: "info" | "warn"; text: string } | null>(null);

  const { state, connection, hello, lastStateAt, notice } = socket;
  const status = statusView(connection, camera.status, state);
  const stale = status.stale;
  const disclosures = state?.disclosures ?? hello?.disclosures ?? DEFAULT_DISCLOSURES;

  useFrameSampler({
    videoRef,
    enabled: camera.status === "active" && connection === "connected",
    canSend: socket.canSendFrame,
    send: socket.sendFrame,
  });

  useEffect(() => {
    if (!notice) return;
    const show = window.setTimeout(() => setVisibleNotice(notice), 0);
    const hide = window.setTimeout(() => setVisibleNotice((n) => (n && n.id === notice.id ? null : n)), NOTICE_MS);
    return () => { window.clearTimeout(show); window.clearTimeout(hide); };
  }, [notice]);

  const fresh = detectionsFresh(connection, camera.status, lastStateAt, now, DETECTION_STALE_MS);
  const zones = state?.zones ?? hello?.zones ?? [];
  const detections = useMemo(() => (fresh && state ? state.detections : []), [fresh, state]);

  const trackingLine = useMemo(() => {
    if (!fresh || !state) return connection === "connected" ? "Analysis active" : "Analysis unavailable (backend disconnected)";
    if (state.vision.status !== "ready") return state.vision.message;
    const focus = state.detections.find((d) => d.in_active_journey) ?? state.detections[0];
    if (!focus) return "No person tracked";
    return `Tracking ID ${focus.tracker_id} (temporary) · ${focus.zone_id ? `Zone ${focus.zone_id}` : "outside the zones"} · conf ${focus.confidence.toFixed(2)}`;
  }, [fresh, state, connection]);

  const analysis = analysisStatus(connection, camera.status, state, fresh);

  const onCommand = useCallback((c: ClientCommand) => {
    if (!socket.sendCommand(c)) socket.pushNotice("warn", "Backend not connected — command not sent.");
  }, [socket]);

  const onSave = useCallback(() => {
    setSaving(true);
    socket.requestEvidence()
      .then((ev) => {
        const name = evidenceFilename(ev);
        downloadJson(ev, name);
        socket.pushNotice("info", `Evidence JSON downloaded: ${name}`);
      })
      .catch((err: unknown) => socket.pushNotice("warn", err instanceof Error ? err.message : "Evidence export failed."))
      .finally(() => setSaving(false));
  }, [socket]);

  const steps = state?.step_states ?? FALLBACK_EXPECTED.map((f) => ({
    step_id: f.step_id, name: f.name, state: "NOT_REACHED", indicator: "NOT REACHED" as const, word: "",
  }));

  return (
    <div className="flex min-h-screen flex-col xl:h-screen xl:min-h-[44rem]">
      <AppHeader status={status} mode={mode} onMode={changeMode} analysis={analysis}
        engineVersion={mode === "operator" && health?.ok ? health.engineVersion : null} />

      {health?.ok && health.websocketSupport === false && (
        <div role="alert" className="flex items-center gap-2 border-b border-ember bg-ember-soft px-6 py-2 text-sm font-bold text-ember-deep">
          <TriangleAlert aria-hidden className="size-4" />
          The backend is running without WebSocket support. Install it with: pip install -e &quot;.[web]&quot; and restart uvicorn.
        </div>
      )}

      {stale && (
        <div role="alert" className="flex items-center gap-2 border-b border-ember bg-ember-soft px-6 py-1.5 text-sm font-bold text-ember-deep">
          <TriangleAlert aria-hidden className="size-4" />
          {status.staleReason}
          {connection === "disconnected" && " Reconnecting automatically; a reconnect starts a new journey."}
        </div>
      )}

      <main className="flex min-h-0 flex-1 flex-col gap-3 p-4 short:gap-2 short:p-3 2xl:gap-4 2xl:p-5">
        <div className="grid min-h-[30rem] flex-1 grid-rows-[minmax(0,1fr)] gap-3 short:min-h-[22rem] xl:grid-cols-[minmax(0,1.45fr)_minmax(21rem,1fr)] 2xl:gap-4">
          <div className="flex min-h-0 min-w-0 flex-col gap-3">
            <CameraPanel
              videoRef={videoRef} stream={camera.stream} cameraStatus={camera.status} cameraError={camera.error}
              permission={camera.permission} onStart={camera.start} onStop={camera.stop}
              zones={zones} activeZone={fresh ? state?.active_zone ?? null : null} detections={detections}
              showDetections={fresh} trackingLine={trackingLine}
            />
            <EvidenceTracks expected={state?.expected ?? FALLBACK_EXPECTED} physical={state?.physical_trace ?? []}
              digital={state?.digital_trace ?? []} steps={steps} stale={stale} />
          </div>
          <div className="flex min-w-0 flex-col gap-3">
            <VerdictCard verdict={state?.verdict ?? null} violations={state?.violation_types ?? []}
              finding={state?.finding ?? "Enter Zone A to begin a journey."} where={state?.finding_where ?? ""}
              extra={state?.extra_findings ?? 0} stale={stale} staleReason={status.staleReason} />
            <StepStateList steps={steps} stale={stale} />
            {mode === "operator" && (
              <dl className="rounded-xl border border-dashed border-line px-4 py-2 text-xs text-muted">
                <div className="flex justify-between"><dt>Backend</dt><dd>{status.backendLabel}</dd></div>
                <div className="flex justify-between"><dt>Frame</dt><dd>{state?.frame ? `#${state.frame.seq} · ${state.frame.width}×${state.frame.height}` : "—"}</dd></div>
                <div className="flex justify-between"><dt>Vision</dt><dd>{state?.vision.status ?? "—"}</dd></div>
                <div className="flex justify-between"><dt>Journey</dt><dd className="font-mono">{state?.journey_id ? state.journey_id.slice(0, 8) : "—"} (temporary)</dd></div>
              </dl>
            )}
            <div className="flex min-h-[7rem] flex-1 flex-col overflow-hidden">
              <EvidenceTimeline rows={state?.timeline ?? []} stale={stale} />
            </div>
          </div>
        </div>
        <DemoControlsDrawer mode={mode} disabled={connection !== "connected"} onCommand={onCommand} onSave={onSave}
          saving={saving} note={disclosures.digital_note} label={disclosures.digital_label} />
      </main>

      {visibleNotice && (
        <div role="status" className={`fixed bottom-16 left-1/2 z-10 flex max-w-2xl -translate-x-1/2 items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold shadow-lg ${
          visibleNotice.tone === "warn" ? "bg-ember-deep text-cream" : "bg-forest text-cream"}`}>
          {visibleNotice.tone === "warn" ? <TriangleAlert aria-hidden className="size-4" /> : <Info aria-hidden className="size-4" />}
          {visibleNotice.text}
        </div>
      )}

      <PrivacyFooter d={disclosures} />
    </div>
  );
}
