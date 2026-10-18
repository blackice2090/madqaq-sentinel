import { describe, expect, it } from "vitest";

import { CONTROLS, controlFor } from "@/lib/commands";
import { encodeCommand } from "@/lib/protocol";

describe("control -> command mapping (M2 semantics)", () => {
  it("has exactly the five required controls, in order", () => {
    expect(CONTROLS.map((c) => [c.label, c.command])).toEqual([
      ["FULL DIGITAL", "digital_full"],
      ["WITHOUT B", "digital_without_b"],
      ["B FAILED", "digital_b_failed"],
      ["CLEAR DIGITAL", "digital_clear"],
      ["RESET JOURNEY", "reset"],
    ]);
  });
  it("matches the M2 keyboard keys", () => {
    expect(CONTROLS.map((c) => c.m2Key)).toEqual(["1", "2", "3", "0", "R"]);
  });
  it("each control encodes to a valid protocol message", () => {
    for (const c of CONTROLS) expect(JSON.parse(encodeCommand(c.command))).toEqual({ command: c.command });
    expect(controlFor("reset")?.label).toBe("RESET JOURNEY");
  });
  it("digital hints never describe a real external system", () => {
    for (const c of CONTROLS) expect(c.hint.toLowerCase()).not.toMatch(/real|production|government|live checkpoint/);
  });
});
