import { uniqueViolations, verdictView, violationDescription } from "@/lib/format";
import { violationTitle } from "@/lib/presentation";
import type { Verdict, ViolationType } from "@/lib/protocol";

import { ToneIcon, toneText } from "./ToneIcon";

const frame: Record<string, string> = {
  ok: "border-forest/40 bg-forest-soft",
  violation: "border-ember bg-ember-soft",
  uncertain: "border-amber-600/40 bg-amber-50",
  neutral: "border-line bg-white",
  stale: "border-dashed border-muted bg-cream-deep",
};

export function VerdictCard({ verdict, violations, finding, where, extra, stale, staleReason }: {
  verdict: Verdict | null; violations: ViolationType[]; finding: string; where: string; extra: number;
  stale: boolean; staleReason: string | null;
}) {
  const v = verdictView(verdict, stale);
  const types = uniqueViolations(violations);
  const violated = v.tone === "violation" && types.length > 0;
  return (
    <section aria-live="polite" aria-label="Verdict" className={`fade-in rounded-xl border-2 p-5 short:p-3 transition-colors ${frame[v.tone]}`}>
      <h2 className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">Verdict</h2>
      <div className="mt-1 flex items-center gap-3">
        <ToneIcon tone={v.tone} className="size-9" />
        <p className={`text-4xl font-black tracking-wide short:text-3xl 2xl:text-5xl ${v.tone === "uncertain" ? "text-amber-800" : toneText[v.tone]}`}>{v.label}</p>
      </div>
      {stale ? (
        <p className="mt-3 text-base font-medium text-muted">{staleReason}{verdict ? ` Last received verdict: ${verdict}.` : ""}</p>
      ) : (
        <>
          {violated && (
            <p className="mt-2 text-xl font-extrabold short:mt-1 short:text-lg tracking-wide text-ember-deep" title={violationDescription(types[0]!)}>
              {violationTitle(types)}
            </p>
          )}
          {where && violated && <p className="mt-1 text-base font-semibold text-ink">Step {where}</p>}
          <p className="mt-2 text-base leading-snug text-ink short:mt-1 short:text-sm 2xl:text-lg">{finding}</p>
          {extra > 0 && <p className="mt-1 text-sm text-muted">+{extra} more finding{extra > 1 ? "s" : ""}</p>}
          {!violated && where && <p className="mt-1 text-sm text-muted">At: {where}</p>}
        </>
      )}
    </section>
  );
}
