import { describe, expect, it } from "vitest";

import {
  channelLabel, formatConfidence, stepIndicatorView, uniqueViolations, verdictView, violationLabel,
} from "@/lib/format";

describe("verdict formatting", () => {
  it("maps each verdict to a word and a tone (never colour alone)", () => {
    expect(verdictView("COMPLETED", false)).toMatchObject({ label: "COMPLETED", tone: "ok" });
    expect(verdictView("VIOLATED", false)).toMatchObject({ label: "VIOLATED", tone: "violation" });
    expect(verdictView("UNCERTAIN", false)).toMatchObject({ label: "UNCERTAIN", tone: "uncertain" });
    expect(verdictView("WAITING", false).label).toBe("WAITING");
    expect(verdictView(null, false).label).toBe("WAITING");
  });
  it("never shows a live verdict when results are stale", () => {
    expect(verdictView("COMPLETED", true)).toMatchObject({ label: "UNAVAILABLE", tone: "stale" });
  });
});

describe("violation labels", () => {
  it("are human readable", () => {
    expect(violationLabel("OMISSION")).toBe("OMISSION");
    expect(violationLabel("ORDER_INVERSION")).toBe("ORDER INVERSION");
    expect(violationLabel("PHANTOM_COMPLETION")).toBe("PHANTOM COMPLETION");
    expect(violationLabel("CHANNEL_CONTRADICTION")).toBe("CHANNEL CONTRADICTION");
  });
  it("de-duplicates in engine order", () => {
    expect(uniqueViolations(["PHANTOM_COMPLETION", "OMISSION", "PHANTOM_COMPLETION"])).toEqual(["PHANTOM_COMPLETION", "OMISSION"]);
  });
});

describe("step indicators", () => {
  it("OK reads CONFIRMED", () => {
    expect(stepIndicatorView("OK")).toEqual({ label: "CONFIRMED", tone: "ok" });
    expect(stepIndicatorView("CONFLICT").tone).toBe("violation");
    expect(stepIndicatorView("NOT REACHED").label).toBe("NOT REACHED");
  });
});

describe("small formatters", () => {
  it("labels simulated digital rows", () => {
    expect(channelLabel("DIGITAL", true)).toBe("DIGITAL (SIMULATED)");
    expect(channelLabel("PHYSICAL", false)).toBe("PHYSICAL");
  });
  it("formats confidence", () => {
    expect(formatConfidence(null)).toBe("—");
    expect(formatConfidence(0.8712)).toBe("0.87");
  });
});
