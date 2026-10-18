import type { ReactNode } from "react";

export function Panel({ title, aside, children, className = "" }: {
  title: string; aside?: ReactNode; children: ReactNode; className?: string;
}) {
  return (
    <section className={`rounded-xl border border-line bg-white/70 p-4 ${className}`}>
      <header className="mb-3 flex items-center justify-between gap-3">
        <h2 className="text-[0.8rem] font-bold uppercase tracking-[0.14em] text-forest">{title}</h2>
        {aside}
      </header>
      {children}
    </section>
  );
}

export function SimulatedBadge() {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-md border-2 border-ember bg-ember-soft px-2 py-0.5 text-[0.72rem] font-extrabold uppercase tracking-[0.12em] text-ember-deep">
      SIMULATED DIGITAL CHANNEL
    </span>
  );
}
