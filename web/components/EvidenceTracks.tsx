import { X } from "lucide-react";

import { buildTracks, type CellKind, type TrackCell } from "@/lib/presentation";
import type { DigitalTraceItem, StepStateRow } from "@/lib/protocol";

import { SimulatedBadge } from "./StatusPill";

const CELL_TEXT: Record<CellKind, string> = {
  present: "recorded", absent: "no evidence", missing: "missing", failed: "failed", pending: "pending",
};
const LABEL_COL = "8rem minmax(0,1fr)";

function EvidenceTrackCell({ cell, index, count, track }: { cell: TrackCell; index: number; count: number; track: string }) {
  const k = cell.kind;
  const style =
    k === "present" ? "border-forest bg-forest text-cream"
      : k === "failed" ? "border-ember bg-ember-soft text-ember-deep"
        : k === "missing" ? "border-dashed border-ember bg-white text-ember-deep"
          : "border-dashed border-line bg-white text-muted";
  return (
    <div role="listitem" aria-label={`${track} step ${cell.step_id}: ${CELL_TEXT[k]}`}
      className="relative flex flex-col items-center justify-center py-1.5 snug:py-0.5 short:py-0">
      <span aria-hidden className={`absolute top-1/2 h-0.5 -translate-y-px bg-line ${index === 0 ? "left-1/2" : "left-0"} ${index === count - 1 ? "right-1/2" : "right-0"}`} />
      <span className={`relative z-10 inline-flex size-12 snug:size-10 short:size-9 items-center justify-center rounded-full border-2 font-mono text-xl snug:text-lg short:text-base font-extrabold transition-colors ${style}`}>
        {k === "missing" ? <X aria-hidden className="size-6" /> : cell.step_id}
      </span>
      {(k === "failed" || k === "missing") && (
        <span className="relative z-10 mt-0.5 text-sm font-bold uppercase tracking-wide text-ember-deep">
          {k === "failed" ? "FAILED" : "MISSING"}
        </span>
      )}
    </div>
  );
}

function EvidenceTrackRow({ label, cells, badge, dim }: { label: string; cells: TrackCell[]; badge?: boolean; dim: boolean }) {
  return (
    <div className="grid items-center gap-2" style={{ gridTemplateColumns: LABEL_COL }}>
      <div>
        <p className="text-base font-bold tracking-[0.1em] text-forest">{label}</p>
        {badge && <SimulatedBadge label="SIMULATED" />}
      </div>
      <div role="list" aria-label={`${label} track`} className={`grid transition-opacity ${dim ? "opacity-50" : ""}`}
        style={{ gridTemplateColumns: `repeat(${Math.max(cells.length, 1)}, minmax(0,1fr))` }}>
        {cells.map((c, i) => <EvidenceTrackCell key={c.step_id} cell={c} index={i} count={cells.length} track={label} />)}
      </div>
    </div>
  );
}

export function EvidenceTracks({ expected, physical, digital, steps, stale }: {
  expected: { step_id: string; name: string }[]; physical: string[]; digital: DigitalTraceItem[];
  steps: StepStateRow[]; stale: boolean;
}) {
  const t = buildTracks(expected, physical, digital, steps);
  return (
    <section aria-label="Evidence tracks" className="rounded-xl border border-line bg-white px-5 py-4 snug:py-2 short:py-1.5">
      <div className="space-y-1 short:space-y-0">
        <EvidenceTrackRow label="EXPECTED" cells={t.expected} dim={false} />
        <EvidenceTrackRow label="PHYSICAL" cells={t.physical} dim={stale} />
        <EvidenceTrackRow label="DIGITAL" cells={t.digital} badge dim={stale} />
        {!stale && t.conflicts.length > 0 && (
          <div className="grid gap-2" style={{ gridTemplateColumns: LABEL_COL }}>
            <span />
            <div className="grid" style={{ gridTemplateColumns: `repeat(${t.expected.length}, minmax(0,1fr))` }}>
              {t.expected.map((e) => (
                <div key={e.step_id} className="text-center text-sm font-extrabold tracking-wider text-ember-deep">
                  {t.conflicts.includes(e.step_id) ? "↑ CONFLICT" : ""}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
