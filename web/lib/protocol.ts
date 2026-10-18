/**
 * Typed WebSocket protocol `madqaq-web/1` (see docs/M6_WEB_DASHBOARD.md).
 * Every server message is validated before use; anything malformed is dropped.
 */

export const PROTOCOL_VERSION = "madqaq-web/1";

export type Verdict = "WAITING" | "IN PROGRESS" | "COMPLETED" | "VIOLATED" | "UNCERTAIN";
export type ViolationType = "OMISSION" | "ORDER_INVERSION" | "PHANTOM_COMPLETION" | "CHANNEL_CONTRADICTION";
export type StepIndicator = "OK" | "MISSING" | "CONFLICT" | "UNCERTAIN" | "NOT REACHED";
export type VisionStatus = "idle" | "loading" | "ready" | "unavailable";
export type Channel = "PHYSICAL" | "DIGITAL";

export const VERDICTS: readonly Verdict[] = ["WAITING", "IN PROGRESS", "COMPLETED", "VIOLATED", "UNCERTAIN"];
export const VIOLATION_TYPES: readonly ViolationType[] = [
  "OMISSION", "ORDER_INVERSION", "PHANTOM_COMPLETION", "CHANNEL_CONTRADICTION",
];
export const STEP_INDICATORS: readonly StepIndicator[] = ["OK", "MISSING", "CONFLICT", "UNCERTAIN", "NOT REACHED"];

export interface Zone { zone_id: string; name: string; x1: number; y1: number; x2: number; y2: number }
export type Box = [number, number, number, number];
export interface Detection {
  tracker_id: number; confidence: number; box: Box; zone_id: string | null; in_active_journey: boolean;
}
export interface StepStateRow { step_id: string; name: string; state: string; indicator: StepIndicator; word: string }
export interface TimelineRow {
  event_id: string; timestamp: string; channel: Channel; step_id: string; step_name: string;
  event_type: string; confidence: number | null; simulated: boolean;
}
export interface Disclosures {
  digital_label: string; digital_note: string; digital_long: string; privacy: string; frames: string;
  frames_storage: string;
}
export interface FrameInfo { width: number; height: number; seq: number }
export interface DigitalTraceItem { step_id: string; failed: boolean }

export interface SessionState {
  type: "state";
  protocol: string;
  session_id: string;
  journey_id: string | null;
  frame: FrameInfo | null;
  vision: { status: VisionStatus; message: string };
  detections: Detection[];
  zones: Zone[];
  active_zone: string | null;
  expected: { step_id: string; name: string }[];
  physical_trace: string[];
  digital_trace: DigitalTraceItem[];
  step_states: StepStateRow[];
  verdict: Verdict;
  engine_status: string | null;
  violation_types: ViolationType[];
  violation_labels: string[];
  finding: string;
  finding_where: string;
  extra_findings: number;
  timeline: TimelineRow[];
  digital_active: boolean;
  digital_simulated: boolean;
  notice: string | null;
  disclosures: Disclosures;
}

export interface HelloMessage {
  type: "hello"; protocol: string; session_id: string; zones: Zone[]; digital_simulated: boolean;
  disclosures: Disclosures;
  recommended: { sample_fps: number; max_width: number; jpeg_quality: number };
  limits: { max_frame_bytes: number; max_frame_width: number; max_frame_height: number; max_text_bytes: number };
}
export interface AckMessage { type: "ack"; command: string; ok: boolean; message: string }
export interface ErrorMessage { type: "error"; code: string; message: string }
export interface PongMessage { type: "pong"; session_id: string }
export interface EvidenceMessage { type: "evidence"; evidence: Record<string, unknown> }
export type ServerMessage = HelloMessage | SessionState | AckMessage | ErrorMessage | PongMessage | EvidenceMessage;

export type ClientCommand =
  | "reset" | "digital_full" | "digital_without_b" | "digital_b_failed" | "digital_clear" | "ping" | "get_evidence";
export const CLIENT_COMMANDS: readonly ClientCommand[] = [
  "reset", "digital_full", "digital_without_b", "digital_b_failed", "digital_clear", "ping", "get_evidence",
];

/** The only text messages the client ever sends. */
export function encodeCommand(command: ClientCommand): string {
  if (!CLIENT_COMMANDS.includes(command)) throw new Error(`unknown command ${String(command)}`);
  return JSON.stringify({ command });
}

// ---- validation -----------------------------------------------------------------
type Obj = Record<string, unknown>;
const isObj = (v: unknown): v is Obj => typeof v === "object" && v !== null && !Array.isArray(v);
const isStr = (v: unknown): v is string => typeof v === "string";
const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const isBool = (v: unknown): v is boolean => typeof v === "boolean";
const isStrOrNull = (v: unknown): v is string | null => v === null || isStr(v);
const isArr = <T>(v: unknown, item: (x: unknown) => x is T): v is T[] => Array.isArray(v) && v.every(item);
const unit = (v: unknown): v is number => isNum(v) && v >= 0 && v <= 1;

export function isZone(v: unknown): v is Zone {
  return isObj(v) && isStr(v.zone_id) && isStr(v.name) && unit(v.x1) && unit(v.y1) && unit(v.x2) && unit(v.y2)
    && (v.x1 as number) < (v.x2 as number) && (v.y1 as number) < (v.y2 as number);
}
function isDetection(v: unknown): v is Detection {
  return isObj(v) && isNum(v.tracker_id) && unit(v.confidence) && Array.isArray(v.box) && v.box.length === 4
    && v.box.every(unit) && isStrOrNull(v.zone_id) && isBool(v.in_active_journey);
}
function isStepRow(v: unknown): v is StepStateRow {
  return isObj(v) && isStr(v.step_id) && isStr(v.name) && isStr(v.state) && isStr(v.word)
    && STEP_INDICATORS.includes(v.indicator as StepIndicator);
}
function isTimelineRow(v: unknown): v is TimelineRow {
  return isObj(v) && isStr(v.event_id) && isStr(v.timestamp) && (v.channel === "PHYSICAL" || v.channel === "DIGITAL")
    && isStr(v.step_id) && isStr(v.step_name) && isStr(v.event_type)
    && (v.confidence === null || isNum(v.confidence)) && isBool(v.simulated);
}
function isDisclosures(v: unknown): v is Disclosures {
  return isObj(v) && ["digital_label", "digital_note", "digital_long", "privacy", "frames", "frames_storage"]
    .every((k) => isStr(v[k]));
}
function isFrame(v: unknown): v is FrameInfo | null {
  return v === null || (isObj(v) && isNum(v.width) && isNum(v.height) && isNum(v.seq) && v.width > 0 && v.height > 0);
}

export function isSessionState(v: unknown): v is SessionState {
  if (!isObj(v) || v.type !== "state") return false;
  const vision = v.vision;
  return isStr(v.protocol) && isStr(v.session_id) && isStrOrNull(v.journey_id) && isFrame(v.frame)
    && isObj(vision) && ["idle", "loading", "ready", "unavailable"].includes(vision.status as string) && isStr(vision.message)
    && isArr(v.detections, isDetection) && isArr(v.zones, isZone) && isStrOrNull(v.active_zone)
    && isArr(v.expected, (e): e is { step_id: string; name: string } => isObj(e) && isStr(e.step_id) && isStr(e.name))
    && isArr(v.physical_trace, isStr)
    && isArr(v.digital_trace, (d): d is DigitalTraceItem => isObj(d) && isStr(d.step_id) && isBool(d.failed))
    && isArr(v.step_states, isStepRow) && VERDICTS.includes(v.verdict as Verdict) && isStrOrNull(v.engine_status)
    && isArr(v.violation_types, (t): t is ViolationType => VIOLATION_TYPES.includes(t as ViolationType))
    && isArr(v.violation_labels, isStr) && isStr(v.finding) && isStr(v.finding_where) && isNum(v.extra_findings)
    && isArr(v.timeline, isTimelineRow) && isBool(v.digital_active) && isBool(v.digital_simulated)
    && isStrOrNull(v.notice) && isDisclosures(v.disclosures);
}

export function parseServerMessage(raw: unknown): ServerMessage | null {
  let data: unknown = raw;
  if (isStr(raw)) {
    try { data = JSON.parse(raw); } catch { return null; }
  }
  if (!isObj(data) || !isStr(data.type)) return null;
  switch (data.type) {
    case "state":
      return isSessionState(data) ? data : null;
    case "hello":
      return isStr(data.protocol) && isStr(data.session_id) && isArr(data.zones, isZone) && isBool(data.digital_simulated)
        && isDisclosures(data.disclosures) && isObj(data.recommended) && isObj(data.limits)
        ? (data as unknown as HelloMessage) : null;
    case "ack":
      return isStr(data.command) && isBool(data.ok) && isStr(data.message) ? (data as unknown as AckMessage) : null;
    case "error":
      return isStr(data.code) && isStr(data.message) ? (data as unknown as ErrorMessage) : null;
    case "pong":
      return isStr(data.session_id) ? (data as unknown as PongMessage) : null;
    case "evidence":
      return isObj(data.evidence) ? (data as unknown as EvidenceMessage) : null;
    default:
      return null;
  }
}
