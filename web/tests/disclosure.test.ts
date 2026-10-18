import { readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

import { DEFAULT_DISCLOSURES } from "@/lib/disclosures";
import { evidenceFilename, evidenceIsDisclosed } from "@/lib/evidence";

import { sampleState } from "./fixtures";

describe("simulated digital disclosure", () => {
  it("uses the exact required wording", () => {
    expect(DEFAULT_DISCLOSURES.digital_label).toBe("SIMULATED DIGITAL CHANNEL");
    expect(DEFAULT_DISCLOSURES.digital_note).toBe("Local simulator — not a production checkpoint integration.");
    expect(DEFAULT_DISCLOSURES.privacy).toBe("Temporary tracking only • No face recognition • No persistent identity");
    expect(DEFAULT_DISCLOSURES.frames).toBe(
      "Sampled camera frames are sent to the local MADQAQ analysis backend while the web demo is active.");
  });
  it("frontend defaults match what the backend sends", () => {
    expect(sampleState().disclosures).toEqual(DEFAULT_DISCLOSURES);
  });
  it("evidence exports must keep the disclosure", () => {
    expect(evidenceIsDisclosed({ digital_simulated: true, disclosures: DEFAULT_DISCLOSURES })).toBe(true);
    expect(evidenceIsDisclosed({ digital_simulated: false, disclosures: DEFAULT_DISCLOSURES })).toBe(false);
    expect(evidenceIsDisclosed({ digital_simulated: true })).toBe(false);
  });
  it("evidence filenames are safe", () => {
    const name = evidenceFilename({ verdict: "VIOLATED", violation_types: ["PHANTOM_COMPLETION", "../x"] },
      new Date(2026, 9, 17, 9, 5, 7));
    expect(name).toBe("madqaq-evidence_2026-10-17_090507_PHANTOM_COMPLETION____x.json");
    expect(name).not.toContain("/");
  });
});

/** The UI must never show forbidden M5 claims, and the simulated channel must never be presented as real. */
describe("claims hygiene in UI source", () => {
  const files: string[] = [];
  const walk = (dir: string) => {
    for (const f of readdirSync(dir)) {
      const p = path.join(dir, f);
      if (statSync(p).isDirectory()) walk(p);
      else if (/\.(tsx?|css)$/.test(f)) files.push(p);
    }
  };
  ["app", "components", "lib", "hooks"].forEach((d) => walk(path.resolve(d)));
  it.each(["95% camera accuracy", "98.1% accuracy", "production ready", "field validated", "real checkpoint system"])(
    "no source file contains %j", (phrase) => {
      for (const f of files) expect(readFileSync(f, "utf8").toLowerCase()).not.toContain(phrase);
    });
  it("the evidence tracks and controls drawer show the simulated badge; the footer states it once", () => {
    const tracks = readFileSync(path.resolve("components/EvidenceTracks.tsx"), "utf8");
    const controls = readFileSync(path.resolve("components/DemoControlsDrawer.tsx"), "utf8");
    const footer = readFileSync(path.resolve("components/PrivacyFooter.tsx"), "utf8");
    expect(tracks).toContain("<SimulatedBadge");
    expect(controls).toContain("<SimulatedBadge");
    expect(footer).toContain("Digital channel is simulated for demonstration.");
  });
});
