import type { SessionState } from "@/lib/protocol";
import { DEFAULT_DISCLOSURES } from "@/lib/disclosures";

/** A state message shaped exactly like apps/web_api/session.py WebSession.state(). */
export function sampleState(overrides: Partial<SessionState> = {}): SessionState {
  return {
    type: "state",
    protocol: "madqaq-web/1",
    session_id: "5d8f2a6e-0000-4000-8000-000000000001",
    journey_id: "0b6c1e2a-0000-4000-8000-000000000002",
    frame: { width: 960, height: 540, seq: 12 },
    vision: { status: "ready", message: "Person detection active." },
    detections: [{ tracker_id: 3, confidence: 0.87, box: [0.3, 0.2, 0.42, 0.95], zone_id: "B", in_active_journey: true }],
    zones: [
      { zone_id: "A", name: "Entry", x1: 0.02, y1: 0.1, x2: 0.24, y2: 1 },
      { zone_id: "B", name: "Credential Check", x1: 0.27, y1: 0.1, x2: 0.49, y2: 1 },
      { zone_id: "C", name: "Screening", x1: 0.52, y1: 0.1, x2: 0.74, y2: 1 },
      { zone_id: "D", name: "Exit", x1: 0.76, y1: 0.1, x2: 0.98, y2: 1 },
    ],
    active_zone: "B",
    expected: [
      { step_id: "A", name: "Entry" }, { step_id: "B", name: "Credential Check" },
      { step_id: "C", name: "Screening" }, { step_id: "D", name: "Exit" },
    ],
    physical_trace: ["A", "C", "D"],
    digital_trace: [{ step_id: "A", failed: false }, { step_id: "B", failed: false }, { step_id: "C", failed: false }, { step_id: "D", failed: false }],
    step_states: [
      { step_id: "A", name: "Entry", state: "CONFIRMED", indicator: "OK", word: "Confirmed" },
      { step_id: "B", name: "Credential Check", state: "INCOMPLETE", indicator: "CONFLICT", word: "Digital only" },
      { step_id: "C", name: "Screening", state: "CONFIRMED", indicator: "OK", word: "Confirmed" },
      { step_id: "D", name: "Exit", state: "CONFIRMED", indicator: "OK", word: "Confirmed" },
    ],
    verdict: "VIOLATED",
    engine_status: "VIOLATED",
    violation_types: ["PHANTOM_COMPLETION"],
    violation_labels: ["PHANTOM COMPLETION"],
    finding: "Credential Check was recorded digitally, but no supporting physical evidence was observed.",
    finding_where: "B — Credential Check",
    extra_findings: 0,
    timeline: [
      { event_id: "e1", timestamp: "2026-10-17T12:00:01+00:00", channel: "PHYSICAL", step_id: "A", step_name: "Entry", event_type: "observed", confidence: 0.91, simulated: false },
      { event_id: "e2", timestamp: "2026-10-17T12:00:09+00:00", channel: "DIGITAL", step_id: "B", step_name: "Credential Check", event_type: "completed", confidence: null, simulated: true },
    ],
    digital_active: true,
    digital_simulated: true,
    notice: null,
    disclosures: DEFAULT_DISCLOSURES,
    ...overrides,
  };
}
