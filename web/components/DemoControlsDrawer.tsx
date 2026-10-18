import { ChevronDown, ChevronUp, Download, Eraser, RotateCcw, Send } from "lucide-react";
import { useState } from "react";

import { CONTROLS } from "@/lib/commands";
import type { UiMode } from "@/lib/presentation";
import type { ClientCommand } from "@/lib/protocol";

import { SimulatedBadge } from "./StatusPill";

export function DemoControlsDrawer({ mode, disabled, onCommand, onSave, saving, note, label }: {
  mode: UiMode; disabled: boolean; onCommand: (c: ClientCommand) => void; onSave: () => void; saving: boolean;
  note: string; label: string;
}) {
  const [manual, setManual] = useState(false);
  const open = mode === "operator" || manual;
  return (
    <section aria-label="Demo controls" className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-3">
        <button type="button" aria-expanded={open} aria-controls="demo-controls-panel"
          disabled={mode === "operator"} onClick={() => setManual((m) => !m)}
          className="inline-flex items-center gap-2 rounded-lg px-2 py-1 text-sm font-semibold tracking-wide text-forest hover:bg-cream-deep disabled:cursor-default disabled:hover:bg-transparent">
          DEMO CONTROLS {open ? <ChevronUp aria-hidden className="size-4" /> : <ChevronDown aria-hidden className="size-4" />}
        </button>
        <button type="button" disabled={disabled || saving} onClick={onSave}
          className="inline-flex items-center gap-2 rounded-lg border border-forest px-3 py-1.5 text-sm font-bold tracking-wide text-forest hover:bg-forest hover:text-cream disabled:cursor-not-allowed disabled:opacity-45">
          <Download aria-hidden className="size-4" /> SAVE EVIDENCE
        </button>
      </div>
      {open && (
        <div id="demo-controls-panel" className="fade-in flex flex-wrap items-center gap-2">
          <SimulatedBadge label={label} />
          {CONTROLS.map((c) => (
            <button key={c.command} type="button" disabled={disabled} title={`${c.hint} (M2 key ${c.m2Key})`}
              onClick={() => onCommand(c.command)}
              className={`inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-bold tracking-wide disabled:cursor-not-allowed disabled:opacity-45 ${
                c.kind === "reset" ? "border-2 border-forest text-forest hover:bg-forest-soft"
                  : c.command === "digital_clear" ? "border border-line bg-cream-deep text-ink hover:bg-line"
                    : "bg-forest text-cream hover:bg-forest-deep"}`}>
              {c.kind === "reset" ? <RotateCcw aria-hidden className="size-4" />
                : c.command === "digital_clear" ? <Eraser aria-hidden className="size-4" /> : <Send aria-hidden className="size-4" />}
              {c.label}
            </button>
          ))}
          <span className="text-sm text-muted">{note}</span>
        </div>
      )}
    </section>
  );
}
