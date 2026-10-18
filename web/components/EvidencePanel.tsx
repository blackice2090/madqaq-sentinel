import { ArrowRight, CircleX } from "lucide-react";

import type { DigitalTraceItem } from "@/lib/protocol";

import { Panel, SimulatedBadge } from "./Panel";

function Chip({ id, name, failed = false, muted = false }: { id: string; name?: string; failed?: boolean; muted?: boolean }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-base font-semibold ${
      failed ? "border-ember bg-ember-soft text-ember-deep" : muted ? "border-line bg-cream text-ink" : "border-forest/30 bg-forest-soft text-forest"}`}>
      <span className="font-mono text-lg font-extrabold">{id}</span>
      {name && <span className="text-sm font-medium">{name}</span>}
      {failed && <><CircleX aria-hidden className="size-4" /><span className="text-xs font-extrabold">FAILED</span></>}
    </span>
  );
}

function Trace({ items, empty }: { items: React.ReactNode[]; empty: string }) {
  if (items.length === 0) return <p className="py-1 text-sm italic text-muted">{empty}</p>;
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {items.map((node, i) => (
        <span key={i} className="inline-flex items-center gap-1.5">
          {i > 0 && <ArrowRight aria-hidden className="size-4 text-muted" />}
          {node}
        </span>
      ))}
    </div>
  );
}

export function EvidencePanel({ expected, physical, digital, digitalNote, stale }: {
  expected: { step_id: string; name: string }[];
  physical: string[];
  digital: DigitalTraceItem[];
  digitalNote: string;
  stale: boolean;
}) {
  return (
    <Panel title="Expected Procedure">
      <Trace items={expected.map((s) => <Chip key={s.step_id} id={s.step_id} name={s.name} muted />)} empty="—" />
      <div className={`mt-4 space-y-3 ${stale ? "opacity-50" : ""}`}>
        <div>
          <h3 className="mb-1 text-xs font-bold uppercase tracking-[0.14em] text-muted">Physical Evidence · camera</h3>
          <Trace items={physical.map((s, i) => <Chip key={`${s}-${i}`} id={s} />)} empty="No physical events yet." />
        </div>
        <div>
          <div className="mb-1 flex flex-wrap items-center gap-2">
            <h3 className="text-xs font-bold uppercase tracking-[0.14em] text-muted">Digital Evidence</h3>
            <SimulatedBadge />
          </div>
          <Trace items={digital.map((d, i) => <Chip key={`${d.step_id}-${i}`} id={d.step_id} failed={d.failed} />)}
            empty="No simulated digital events." />
          <p className="mt-1 text-xs text-muted">{digitalNote}</p>
        </div>
      </div>
    </Panel>
  );
}
