import { stepIndicatorView } from "@/lib/format";
import type { StepStateRow } from "@/lib/protocol";

import { Panel } from "./Panel";
import { ToneIcon, toneText } from "./ToneIcon";

export function StepStatesPanel({ steps, stale }: { steps: StepStateRow[]; stale: boolean }) {
  return (
    <Panel title="Step States">
      <ul className={`divide-y divide-line ${stale ? "opacity-50" : ""}`}>
        {steps.map((s) => {
          const v = stepIndicatorView(s.indicator);
          return (
            <li key={s.step_id} className="flex items-center justify-between gap-3 py-1.5">
              <span className="text-base"><span className="mr-2 font-mono font-extrabold text-forest">{s.step_id}</span>{s.name}</span>
              <span className={`inline-flex items-center gap-1.5 text-sm font-extrabold tracking-wide ${toneText[v.tone]}`}>
                <ToneIcon tone={v.tone} className="size-4" />
                {v.label}
                {s.word && s.word.toUpperCase() !== v.label && (
                  <span className="font-medium normal-case tracking-normal text-muted">· {s.word}</span>
                )}
              </span>
            </li>
          );
        })}
      </ul>
    </Panel>
  );
}
