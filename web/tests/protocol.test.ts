import { describe, expect, it } from "vitest";

import { CLIENT_COMMANDS, encodeCommand, parseServerMessage } from "@/lib/protocol";

import { sampleState } from "./fixtures";

describe("parseServerMessage", () => {
  it("accepts a valid state message (string or object)", () => {
    const s = sampleState();
    expect(parseServerMessage(JSON.stringify(s))).toEqual(s);
    expect(parseServerMessage(s)?.type).toBe("state");
  });

  it("accepts a waiting state with no journey and no frame", () => {
    const s = sampleState({ journey_id: null, frame: null, verdict: "WAITING", engine_status: null, detections: [],
      violation_types: [], violation_labels: [], timeline: [], physical_trace: [], digital_trace: [], active_zone: null });
    expect(parseServerMessage(s)).not.toBeNull();
  });

  it.each([
    ["unknown verdict", { verdict: "PASSED" }],
    ["unknown violation", { violation_types: ["TAILGATING"] }],
    ["box outside 0..1", { detections: [{ tracker_id: 1, confidence: 0.5, box: [0, 0, 2, 1], zone_id: null, in_active_journey: false }] }],
    ["box with 3 values", { detections: [{ tracker_id: 1, confidence: 0.5, box: [0, 0, 1], zone_id: null, in_active_journey: false }] }],
    ["missing disclosures", { disclosures: undefined }],
    ["non-boolean simulated flag", { digital_simulated: "yes" }],
    ["inverted zone", { zones: [{ zone_id: "A", name: "Entry", x1: 0.5, y1: 0.1, x2: 0.2, y2: 1 }] }],
  ])("rejects a state with %s", (_name, patch) => {
    expect(parseServerMessage({ ...sampleState(), ...patch })).toBeNull();
  });

  it("rejects non-JSON, non-objects and unknown types", () => {
    expect(parseServerMessage("not json")).toBeNull();
    expect(parseServerMessage("[1,2]")).toBeNull();
    expect(parseServerMessage({ type: "exec", code: "x" })).toBeNull();
    expect(parseServerMessage(null)).toBeNull();
  });

  it("parses ack / error / pong / evidence", () => {
    expect(parseServerMessage({ type: "ack", command: "reset", ok: true, message: "Reset" })?.type).toBe("ack");
    expect(parseServerMessage({ type: "error", code: "invalid_image", message: "x" })?.type).toBe("error");
    expect(parseServerMessage({ type: "pong", session_id: "s" })?.type).toBe("pong");
    expect(parseServerMessage({ type: "evidence", evidence: { verdict: "COMPLETED" } })?.type).toBe("evidence");
    expect(parseServerMessage({ type: "ack", command: "reset", ok: "yes", message: "x" })).toBeNull();
  });
});

describe("encodeCommand", () => {
  it("produces exactly {command} for every allowed command", () => {
    for (const c of CLIENT_COMMANDS) expect(JSON.parse(encodeCommand(c))).toEqual({ command: c });
  });
  it("refuses unknown commands", () => {
    // @ts-expect-error - runtime guard for untyped callers
    expect(() => encodeCommand("shutdown")).toThrow();
  });
});
