import { stepIndicatorView } from "@/lib/format";
import { stepNote } from "@/lib/presentation";
import type { StepStateRow } from "@/lib/protocol";

import { ToneIcon, toneText } from "./ToneIcon";

export function StepStateList({ steps, stale }: { steps: StepStateRow[]; stale: boolean }) {
  return (
    <section aria-label="Step states" className="rounded-xl border border-line bg-white p-4 short:px-3 short:py-2">
      <h2 className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">Step states</h2>
      <ul className={`mt-2 short:mt-0 divide-y divide-line/70 transition-opacity ${stale ? "opacity-50" : ""}`}>
        {steps.map((s) => {
          const v = stepIndicatorView(s.indicator);
          const note = stepNote(s, v.label);
          return (
            <li key={s.step_id} className="flex items-center justify-between gap-3 py-2 short:py-0.5">
              <span className="text-base">
                <span className="mr-3 inline-block w-4 font-mono font-extrabold text-forest">{s.step_id}</span>{s.name}
              </span>
              <span className={`inline-flex items-center gap-2 text-sm font-bold tracking-wide transition-colors ${toneText[v.tone]}`}>
                {note && <span className="hidden font-normal normal-case tracking-normal text-muted 2xl:inline">{note}</span>}
                <ToneIcon tone={v.tone} className="size-4" />
                {v.label}
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
