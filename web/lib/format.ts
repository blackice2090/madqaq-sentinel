/** Judge-facing wording for the web UI. Presentation only: never changes engine results. */
import type { StepIndicator, Verdict, ViolationType } from "./protocol";

export type Tone = "ok" | "violation" | "uncertain" | "neutral" | "stale";

export interface VerdictView { label: string; tone: Tone; description: string }

export function verdictView(verdict: Verdict | null, stale: boolean): VerdictView {
  if (stale) return { label: "UNAVAILABLE", tone: "stale", description: "Backend disconnected — results are stale." };
  switch (verdict) {
    case "COMPLETED":
      return { label: "COMPLETED", tone: "ok", description: "Physical and digital evidence agree." };
    case "VIOLATED":
      return { label: "VIOLATED", tone: "violation", description: "A procedure-integrity violation was detected." };
    case "UNCERTAIN":
      return { label: "UNCERTAIN", tone: "uncertain", description: "Awaiting sufficient cross-channel evidence." };
    case "IN PROGRESS":
      return { label: "IN PROGRESS", tone: "neutral", description: "Journey in progress." };
    case "WAITING":
    case null:
    default:
      return { label: "WAITING", tone: "neutral", description: "Enter Zone A to begin a journey." };
  }
}

const VIOLATION_TEXT: Record<ViolationType, { label: string; description: string }> = {
  OMISSION: { label: "OMISSION", description: "A required step was skipped." },
  ORDER_INVERSION: { label: "ORDER INVERSION", description: "A required step occurred out of sequence." },
  PHANTOM_COMPLETION: {
    label: "PHANTOM COMPLETION",
    description: "A step was recorded digitally without supporting physical evidence.",
  },
  CHANNEL_CONTRADICTION: {
    label: "CHANNEL CONTRADICTION",
    description: "Physical evidence and digital status disagree.",
  },
};

export function violationLabel(type: ViolationType): string {
  return VIOLATION_TEXT[type]?.label ?? String(type).replace(/_/g, " ");
}

export function violationDescription(type: ViolationType): string {
  return VIOLATION_TEXT[type]?.description ?? "";
}

/** De-duplicated, in engine order. */
export function uniqueViolations(types: readonly ViolationType[]): ViolationType[] {
  return Array.from(new Set(types));
}

const STEP_TEXT: Record<StepIndicator, { label: string; tone: Tone }> = {
  OK: { label: "CONFIRMED", tone: "ok" },
  MISSING: { label: "MISSING", tone: "violation" },
  CONFLICT: { label: "CONFLICT", tone: "violation" },
  UNCERTAIN: { label: "UNCERTAIN", tone: "uncertain" },
  "NOT REACHED": { label: "NOT REACHED", tone: "neutral" },
};

export function stepIndicatorView(indicator: StepIndicator): { label: string; tone: Tone } {
  return STEP_TEXT[indicator] ?? { label: indicator, tone: "neutral" };
}

export function formatTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "--:--:--";
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

export function formatConfidence(c: number | null): string {
  return c === null ? "—" : c.toFixed(2);
}

export function channelLabel(channel: "PHYSICAL" | "DIGITAL", simulated: boolean): string {
  return channel === "DIGITAL" && simulated ? "DIGITAL (SIMULATED)" : channel;
}

export function eventLabel(eventType: string): string {
  return eventType.toUpperCase();
}
