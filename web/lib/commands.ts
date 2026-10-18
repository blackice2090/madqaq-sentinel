/** Web controls -> protocol commands. These are the existing M2 simulator controls (keys 1/2/3/0/R). */
import type { ClientCommand } from "./protocol";

export interface Control {
  command: ClientCommand;
  label: string;
  hint: string;
  m2Key: string;
  kind: "digital" | "reset";
}

export const CONTROLS: readonly Control[] = [
  { command: "digital_full", label: "FULL DIGITAL", hint: "Simulated digital trace: A, B, C, D completed", m2Key: "1", kind: "digital" },
  { command: "digital_without_b", label: "WITHOUT B", hint: "Simulated digital trace: A, C, D completed", m2Key: "2", kind: "digital" },
  { command: "digital_b_failed", label: "B FAILED", hint: "Simulated digital trace: A, C, D completed; B failed", m2Key: "3", kind: "digital" },
  { command: "digital_clear", label: "CLEAR DIGITAL", hint: "Remove simulated digital evidence from this journey", m2Key: "0", kind: "digital" },
  { command: "reset", label: "RESET JOURNEY", hint: "Clear this browser session's journey, both channels and verdict", m2Key: "R", kind: "reset" },
];

export function controlFor(command: ClientCommand): Control | undefined {
  return CONTROLS.find((c) => c.command === command);
}
