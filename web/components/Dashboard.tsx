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
import { DEFAULT_DISCLOSURES, PROTOTYPE_NOTE } from "@/lib/disclosures";
import { downloadJson, evidenceFilename } from "@/lib/evidence";
import type { ClientCommand } from "@/lib/protocol";

import { CameraPanel } from "./CameraPanel";
import { ControlsPanel } from "./ControlsPanel";
import { EvidencePanel } from "./EvidencePanel";
import { Header } from "./Header";
import { StepStatesPanel } from "./StepStatesPanel";
import { TimelinePanel } from "./TimelinePanel";
import { VerdictPanel } from "./VerdictPanel";

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
    if (!fresh || !state) return connection === "connected" ? "Waiting for analysis…" : "Analysis unavailable (backend disconnected)";
    if (state.vision.status !== "ready") return state.vision.message;
    const focus = state.detections.find((d) => d.in_active_journey) ?? state.detections[0];
    if (!focus) return "No person tracked";
    return `Tracking ID ${focus.tracker_id} (temporary) · ${focus.zone_id ? `Zone ${focus.zone_id}` : "outside the zones"} · conf ${focus.confidence.toFixed(2)}`;
  }, [fresh, state, connection]);

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

  return (
    <div className="flex min-h-screen flex-col">
      <Header status={status} vision={state?.vision.status ?? null} engineVersion={health?.ok ? health.engineVersion : null} />

      {health?.ok && health.websocketSupport === false && (
        <div role="alert" className="flex items-center gap-2 border-b border-ember bg-ember-soft px-6 py-2 text-sm font-bold text-ember-deep">
          <TriangleAlert aria-hidden className="size-4" />
          The backend is running without WebSocket support. Install it with: pip install -e &quot;.[web]&quot; and restart uvicorn.
        </div>
      )}

      {stale && (
        <div role="alert" className="flex items-center gap-2 border-b border-ember bg-ember-soft px-6 py-2 text-sm font-bold text-ember-deep">
          <TriangleAlert aria-hidden className="size-4" />
          {status.staleReason}
          {connection === "disconnected" && " Reconnecting automatically; a reconnect starts a new journey."}
        </div>
      )}

      <main className="grid flex-1 grid-cols-[minmax(0,1.5fr)_minmax(25rem,1fr)] gap-4 p-4 2xl:gap-5 2xl:p-5">
        <div className="flex min-w-0 flex-col gap-4">
          <CameraPanel
            videoRef={videoRef} stream={camera.stream} cameraStatus={camera.status} cameraError={camera.error}
            permission={camera.permission} onStart={camera.start} onStop={camera.stop}
            zones={zones} activeZone={fresh ? state?.active_zone ?? null : null} detections={detections}
            showDetections={fresh} trackingLine={trackingLine} framesNote={disclosures.frames}
          />
          <ControlsPanel disabled={connection !== "connected"} onCommand={onCommand} onSave={onSave} saving={saving}
            note={disclosures.digital_note} />
          <TimelinePanel rows={state?.timeline ?? []} stale={stale} />
        </div>

        <div className="flex min-w-0 flex-col gap-4">
          <EvidencePanel expected={state?.expected ?? FALLBACK_EXPECTED} physical={state?.physical_trace ?? []}
            digital={state?.digital_trace ?? []} digitalNote={disclosures.digital_note} stale={stale} />
          <StepStatesPanel stale={stale} steps={state?.step_states ?? FALLBACK_EXPECTED.map((s) => ({
            step_id: s.step_id, name: s.name, state: "NOT_REACHED", indicator: "NOT REACHED" as const, word: "",
          }))} />
          <VerdictPanel verdict={state?.verdict ?? null} violations={state?.violation_types ?? []}
            finding={state?.finding ?? "Enter Zone A to begin a journey."} where={state?.finding_where ?? ""}
            extra={state?.extra_findings ?? 0} stale={stale} staleReason={status.staleReason} />
          {state?.journey_id && !stale && (
            <p className="text-xs text-muted">Journey <span className="font-mono">{state.journey_id.slice(0, 8)}</span> · random temporary ID, not a person identifier</p>
          )}
        </div>
      </main>

      {visibleNotice && (
        <div role="status" className={`fixed bottom-16 left-1/2 z-10 flex max-w-2xl -translate-x-1/2 items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold shadow-lg ${
          visibleNotice.tone === "warn" ? "bg-ember-deep text-cream" : "bg-forest text-cream"}`}>
          {visibleNotice.tone === "warn" ? <TriangleAlert aria-hidden className="size-4" /> : <Info aria-hidden className="size-4" />}
          {visibleNotice.text}
        </div>
      )}

      <footer className="flex flex-wrap items-center justify-between gap-x-6 gap-y-1 border-t border-line bg-cream-deep px-6 py-2.5 text-xs text-ink">
        <span className="font-bold">{disclosures.privacy}</span>
        <span>{disclosures.frames} {disclosures.frames_storage}</span>
        <span><strong className="text-ember-deep">{disclosures.digital_label}</strong> — {disclosures.digital_note}</span>
        <span className="text-muted">{PROTOTYPE_NOTE}</span>
      </footer>
    </div>
  );
}
