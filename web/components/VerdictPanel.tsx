import { uniqueViolations, verdictView, violationDescription, violationLabel } from "@/lib/format";
import type { Verdict, ViolationType } from "@/lib/protocol";

import { ToneIcon, toneText } from "./ToneIcon";

const frame: Record<string, string> = {
  ok: "border-forest bg-forest-soft",
  violation: "border-ember bg-ember-soft",
  uncertain: "border-line bg-cream-deep",
  neutral: "border-line bg-white/70",
  stale: "border-dashed border-muted bg-cream-deep",
};

export function VerdictPanel({ verdict, violations, finding, where, extra, stale, staleReason }: {
  verdict: Verdict | null; violations: ViolationType[]; finding: string; where: string; extra: number;
  stale: boolean; staleReason: string | null;
}) {
  const v = verdictView(verdict, stale);
  const types = uniqueViolations(violations);
  return (
    <section className={`rounded-xl border-2 p-4 ${frame[v.tone]}`} aria-live="polite">
      <h2 className="text-[0.8rem] font-bold uppercase tracking-[0.14em] text-forest">Verdict</h2>
      <div className="mt-1 flex items-center gap-3">
        <ToneIcon tone={v.tone} className="size-10" />
        <p className={`text-5xl font-black tracking-wide ${toneText[v.tone]}`}>{v.label}</p>
      </div>
      {stale ? (
        <p className="mt-2 text-sm font-semibold text-muted">{staleReason}{verdict ? ` Last received verdict: ${verdict}.` : ""}</p>
      ) : (
        <>
          {types.length > 0 && (
            <ul className="mt-3 flex flex-wrap gap-2">
              {types.map((t) => (
                <li key={t} title={violationDescription(t)}
                  className="rounded-md bg-ember-deep px-2.5 py-1 text-sm font-extrabold tracking-wider text-cream">
                  {violationLabel(t)}
                </li>
              ))}
            </ul>
          )}
          <div className="mt-3 border-t border-ink/10 pt-3">
            <h3 className="text-xs font-bold uppercase tracking-[0.14em] text-muted">Primary Finding</h3>
            <p className="mt-1 text-xl font-semibold leading-snug text-ink">{finding}</p>
            {where && <p className="mt-1 text-sm font-semibold text-muted">At: {where}{extra > 0 ? ` · +${extra} more finding${extra > 1 ? "s" : ""}` : ""}</p>}
          </div>
        </>
      )}
    </section>
  );
}
