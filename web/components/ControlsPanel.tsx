import { Download, Eraser, RotateCcw, Send } from "lucide-react";

import { CONTROLS } from "@/lib/commands";
import type { ClientCommand } from "@/lib/protocol";

import { SimulatedBadge } from "./Panel";

export function ControlsPanel({ disabled, onCommand, onSave, saving, note }: {
  disabled: boolean; onCommand: (c: ClientCommand) => void; onSave: () => void; saving: boolean; note: string;
}) {
  return (
    <section className="rounded-xl border border-line bg-white/70 p-3">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <h2 className="text-[0.8rem] font-bold uppercase tracking-[0.14em] text-forest">Digital Simulator Controls</h2>
        <SimulatedBadge />
        <span className="text-xs text-muted">{note}</span>
      </div>
      <div className="flex flex-wrap gap-2">
        {CONTROLS.map((c) => (
          <button key={c.command} type="button" disabled={disabled} title={`${c.hint} (M2 key ${c.m2Key})`}
            onClick={() => onCommand(c.command)}
            className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-extrabold tracking-wide disabled:cursor-not-allowed disabled:opacity-45 focus-visible:outline-2 focus-visible:outline-ember ${
              c.kind === "reset" ? "border-2 border-forest text-forest hover:bg-forest-soft"
                : c.command === "digital_clear" ? "border border-line bg-cream text-ink hover:bg-cream-deep"
                  : "bg-forest text-cream hover:bg-forest-deep"}`}>
            {c.kind === "reset" ? <RotateCcw aria-hidden className="size-4" />
              : c.command === "digital_clear" ? <Eraser aria-hidden className="size-4" /> : <Send aria-hidden className="size-4" />}
            {c.label}
          </button>
        ))}
        <button type="button" disabled={disabled || saving} onClick={onSave}
          className="ml-auto inline-flex items-center gap-2 rounded-lg bg-ember px-3 py-2 text-sm font-extrabold tracking-wide text-ink hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-45 focus-visible:outline-2 focus-visible:outline-forest">
          <Download aria-hidden className="size-4" /> SAVE EVIDENCE
        </button>
      </div>
    </section>
  );
}
