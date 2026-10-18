import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { DemoControlsDrawer } from "@/components/DemoControlsDrawer";
import { EvidenceTimeline } from "@/components/EvidenceTimeline";
import { EvidenceTracks } from "@/components/EvidenceTracks";
import { PrivacyFooter } from "@/components/PrivacyFooter";
import { StepStateList } from "@/components/StepStateList";
import { VerdictCard } from "@/components/VerdictCard";
import { statusView } from "@/lib/connection";
import { DEFAULT_DISCLOSURES } from "@/lib/disclosures";
import { analysisStatus, buildTracks, DEFAULT_MODE, parseMode, violationTitle } from "@/lib/presentation";
import { VIOLATION_TYPES, type SessionState } from "@/lib/protocol";

import { sampleState } from "./fixtures";

const noop = () => undefined;
const drawer = (mode: "presentation" | "operator") => renderToStaticMarkup(h(DemoControlsDrawer, {
  mode, disabled: false, onCommand: noop, onSave: noop, saving: false, note: DEFAULT_DISCLOSURES.digital_note,
  label: DEFAULT_DISCLOSURES.digital_label,
}));
const tracks = (s: SessionState, stale = false) => renderToStaticMarkup(h(EvidenceTracks, {
  expected: s.expected, physical: s.physical_trace, digital: s.digital_trace, steps: s.step_states, stale,
}));
const verdict = (s: SessionState, stale = false) => renderToStaticMarkup(h(VerdictCard, {
  verdict: s.verdict, violations: s.violation_types, finding: s.finding, where: s.finding_where,
  extra: s.extra_findings, stale, staleReason: stale ? "Backend disconnected — results are stale and unavailable." : null,
}));

const contradiction = sampleState({
  physical_trace: ["A", "B"],
  digital_trace: [{ step_id: "A", failed: false }, { step_id: "B", failed: true }, { step_id: "C", failed: false }, { step_id: "D", failed: false }],
  violation_types: ["CHANNEL_CONTRADICTION"],
});
const completed = sampleState({
  verdict: "COMPLETED", violation_types: [], physical_trace: ["A", "B", "C", "D"],
  finding: "Physical and digital evidence agree.", finding_where: "",
  step_states: ["A", "B", "C", "D"].map((id, i) => ({
    step_id: id, name: ["Entry", "Credential Check", "Screening", "Exit"][i]!, state: "CONFIRMED", indicator: "OK" as const, word: "Confirmed",
  })),
});
const uncertain = sampleState({ verdict: "UNCERTAIN", violation_types: [], digital_trace: [], finding: "Physical evidence only.", finding_where: "" });

describe("mode", () => {
  it("presentation mode is the default and unknown values fall back to it", () => {
    expect(DEFAULT_MODE).toBe("presentation");
    expect(parseMode(null)).toBe("presentation");
    expect(parseMode("garbage")).toBe("presentation");
    expect(parseMode("operator")).toBe("operator");
  });
  it("operator mode exposes every demo control; presentation mode keeps them collapsed", () => {
    const op = drawer("operator");
    for (const l of ["FULL DIGITAL", "WITHOUT B", "B FAILED", "CLEAR DIGITAL", "RESET JOURNEY", "SAVE EVIDENCE"]) expect(op).toContain(l);
    const pr = drawer("presentation");
    expect(pr).toContain('aria-expanded="false"');
    expect(pr).not.toContain("FULL DIGITAL");
    expect(pr).toContain("SAVE EVIDENCE");
  });
});

describe("disclosures", () => {
  it("presentation mode still shows the simulated channel marker and the footer disclosures", () => {
    expect(tracks(sampleState())).toContain("SIMULATED");
    const f = renderToStaticMarkup(h(PrivacyFooter, { d: DEFAULT_DISCLOSURES }));
    expect(f).toContain("Temporary tracking only • No face recognition • No persistent identity");
    expect(f).toContain("Sampled camera frames are sent to the local MADQAQ analysis backend while the web demo is active.");
    expect(f).toContain("Digital channel is simulated for demonstration.");
    expect(f).toContain("Local simulator — not a production checkpoint integration.");
    expect(f).toContain("Research prototype");
  });
});

describe("evidence tracks", () => {
  it("renders expected / physical / digital as distinct aligned lists", () => {
    const m = tracks(sampleState());
    for (const t of ["EXPECTED track", "PHYSICAL track", "DIGITAL track"]) expect(m).toContain(`aria-label="${t}"`);
  });
  it("phantom completion marks B as physically missing and in conflict", () => {
    const s = sampleState({ physical_trace: ["A", "C", "D"] });
    const t = buildTracks(s.expected, s.physical_trace, s.digital_trace, s.step_states);
    expect(t.physical.find((c) => c.step_id === "B")?.kind).toBe("missing");
    expect(t.digital.find((c) => c.step_id === "B")?.kind).toBe("present");
    expect(t.conflicts).toEqual(["B"]);
    expect(tracks(s)).toContain("↑ CONFLICT");
    expect(tracks(s)).toContain("MISSING");
  });
  it("does not fabricate a missing physical step where the engine reports none", () => {
    const t = buildTracks(completed.expected, completed.physical_trace, completed.digital_trace, completed.step_states);
    expect(t.physical.every((c) => c.kind === "present")).toBe(true);
    expect(t.conflicts).toEqual([]);
  });
  it("channel contradiction marks B as failed digitally and in conflict", () => {
    const t = buildTracks(contradiction.expected, contradiction.physical_trace, contradiction.digital_trace, contradiction.step_states);
    expect(t.digital.find((c) => c.step_id === "B")?.kind).toBe("failed");
    expect(t.conflicts).toContain("B");
    expect(tracks(contradiction)).toContain("FAILED");
  });
});

describe("verdict card", () => {
  it("COMPLETED", () => {
    const m = verdict(completed);
    expect(m).toContain("COMPLETED");
    expect(m).toContain("Physical and digital evidence agree.");
  });
  it("UNCERTAIN is not styled as a violation", () => {
    const m = verdict(uncertain);
    expect(m).toContain("UNCERTAIN");
    expect(m).not.toContain("border-ember ");
    expect(m).not.toContain("text-ember-deep");
  });
  it("VIOLATED shows the violation type, step and finding", () => {
    const m = verdict(sampleState());
    expect(m).toContain("VIOLATED");
    expect(m).toContain("PHANTOM COMPLETION");
    expect(m).toContain("Step B — Credential Check");
    expect(m).toContain("Credential Check was recorded digitally");
  });
  it("never shows raw enum underscores in violation titles", () => {
    for (const t of VIOLATION_TYPES) {
      expect(violationTitle([t])).not.toContain("_");
      expect(verdict(sampleState({ violation_types: [t] }))).not.toMatch(/[A-Z]_[A-Z]/);
    }
  });
  it("disconnected backend marks evidence unavailable and stale", () => {
    expect(statusView("disconnected", "active", sampleState()).stale).toBe(true);
    const m = verdict(sampleState(), true);
    expect(m).toContain("UNAVAILABLE");
    expect(m).toContain("stale");
    expect(tracks(sampleState(), true)).toContain("opacity-50");
    expect(renderToStaticMarkup(h(EvidenceTimeline, { rows: sampleState().timeline, stale: true }))).toContain("opacity-50");
  });
});

describe("analysis status", () => {
  it("never reports waiting during a healthy session", () => {
    const s = sampleState();
    for (const [state, fresh] of [[null, false], [s, true], [s, false]] as const) {
      const a = analysisStatus("connected", "active", state, fresh);
      expect(a.label.toLowerCase()).not.toContain("waiting");
      expect(a.healthy).toBe(true);
    }
    expect(analysisStatus("connected", "active", s, true).label).toBe("ANALYSIS ACTIVE");
    expect(analysisStatus("disconnected", "active", s, false).healthy).toBe(false);
  });
});

describe("structure and keyboard access", () => {
  it("controls are native buttons, none removed from tab order", () => {
    const m = drawer("operator");
    expect(m).not.toContain('tabindex="-1"');
    expect((m.match(/<button type="button"/g) ?? []).length).toBe(7);
  });
  it("critical regions are labelled landmarks", () => {
    const s = sampleState();
    expect(verdict(s)).toContain('aria-label="Verdict"');
    expect(tracks(s)).toContain('aria-label="Evidence tracks"');
    expect(renderToStaticMarkup(h(StepStateList, { steps: s.step_states, stale: false }))).toContain('aria-label="Step states"');
    expect(renderToStaticMarkup(h(EvidenceTimeline, { rows: s.timeline, stale: false }))).toContain('aria-label="Evidence timeline"');
  });
  it("timeline distinguishes simulated digital events", () => {
    const m = renderToStaticMarkup(h(EvidenceTimeline, { rows: sampleState().timeline, stale: false }));
    expect(m).toContain("DIGITAL · SIMULATED");
    expect(m).toContain("PHYSICAL");
  });
  it("step states use the presentation labels", () => {
    const m = renderToStaticMarkup(h(StepStateList, { steps: sampleState().step_states, stale: false }));
    expect(m).toContain("CONFLICT");
    expect(m).toContain("CONFIRMED");
  });
});
