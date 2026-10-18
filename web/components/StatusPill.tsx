import type { ReactNode } from "react";

/** Compact status indicator: always dot/icon + words, never colour alone. */
export function StatusPill({ ok, label, icon, onDark = true }: { ok: boolean; label: string; icon?: ReactNode; onDark?: boolean }) {
  const tone = onDark
    ? ok ? "border-cream/30 text-cream" : "border-ember text-cream"
    : ok ? "border-forest/30 text-forest" : "border-ember text-ember-deep";
  return (
    <span role="status" className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-[0.8rem] font-semibold tracking-wide transition-colors ${tone}`}>
      {icon ?? <span aria-hidden className={`size-2 rounded-full ${ok ? "bg-emerald-400" : "bg-ember"}`} />}
      {label}
    </span>
  );
}

export function SimulatedBadge({ label = "SIMULATED DIGITAL CHANNEL" }: { label?: string }) {
  return (
    <span className="inline-flex items-center rounded-md border border-ember bg-ember-soft px-2 py-0.5 text-[0.7rem] font-bold uppercase tracking-[0.1em] text-ember-deep">
      {label}
    </span>
  );
}
