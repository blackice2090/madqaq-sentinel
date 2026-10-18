/**
 * M6.2 presentation derivations. Pure, UI-only: nothing here changes engine results or protocol semantics.
 * Missing / conflict markers are DERIVED from the step indicators the engine already sent; no physical
 * event is ever fabricated.
 */
import type { ConnectionStatus, CameraStatus } from "./connection";
import type { DigitalTraceItem, SessionState, StepIndicator, StepStateRow, ViolationType } from "./protocol";
import { uniqueViolations, violationLabel } from "./format";

export type UiMode = "presentation" | "operator";
export const DEFAULT_MODE: UiMode = "presentation";
export const MODE_STORAGE_KEY = "madqaq-ui-mode";

export function parseMode(raw: string | null | undefined): UiMode {
  return raw === "operator" ? "operator" : "presentation";
}

/** "PHANTOM_COMPLETION" -> "PHANTOM COMPLETION". Raw enum underscores are never displayed. */
export function violationTitle(types: readonly ViolationType[]): string {
  return uniqueViolations(types).map(violationLabel).join(" · ").replace(/_/g, " ");
}

export type CellKind = "present" | "absent" | "missing" | "failed" | "pending";
export interface TrackCell { step_id: string; kind: CellKind }
export interface EvidenceTracksView {
  expected: TrackCell[];
  physical: TrackCell[];
  digital: TrackCell[];
  /** step ids where the channels disagree (derived from engine step indicators) */
  conflicts: string[];
}

const isProblem = (i: StepIndicator | undefined) => i === "CONFLICT" || i === "MISSING";

export function buildTracks(
  expected: { step_id: string }[], physical: string[], digital: DigitalTraceItem[], steps: StepStateRow[],
): EvidenceTracksView {
  const indicator = (id: string) => steps.find((s) => s.step_id === id)?.indicator;
  const conflicts = expected.map((e) => e.step_id).filter((id) => isProblem(indicator(id)));
  return {
    expected: expected.map((e) => ({ step_id: e.step_id, kind: "present" })),
    physical: expected.map(({ step_id }) => ({
      step_id,
      kind: physical.includes(step_id) ? "present" : conflicts.includes(step_id) ? "missing" : "absent",
    })),
    digital: expected.map(({ step_id }) => {
      const d = digital.find((x) => x.step_id === step_id);
      return { step_id, kind: d ? (d.failed ? "failed" : "present") : "absent" };
    }),
    conflicts,
  };
}

/** Secondary explanation for a step row, only when it adds something beyond the label. */
export function stepNote(row: StepStateRow, label: string): string {
  const w = row.word.trim();
  return w && w.toUpperCase() !== label ? w : "";
}

export interface AnalysisStatus { label: string; healthy: boolean }

/** Never claims "waiting for analysis" while a healthy session simply awaits the next sampled frame. */
export function analysisStatus(
  connection: ConnectionStatus, camera: CameraStatus, state: SessionState | null, fresh: boolean,
): AnalysisStatus {
  if (connection !== "connected") {
    return { label: connection === "connecting" ? "CONNECTING TO BACKEND" : "ANALYSIS UNAVAILABLE", healthy: false };
  }
  if (camera !== "active") return { label: "ANALYSIS IDLE", healthy: false };
  if (!state) return { label: "PROCESSING FRAME", healthy: true };
  if (state.vision.status === "loading") return { label: "LOADING DETECTOR", healthy: false };
  if (state.vision.status === "unavailable") return { label: "DETECTOR UNAVAILABLE", healthy: false };
  return { label: fresh ? "ANALYSIS ACTIVE" : "LATEST ANALYSIS COMPLETE", healthy: true };
}
