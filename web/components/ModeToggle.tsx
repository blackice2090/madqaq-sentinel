import type { UiMode } from "@/lib/presentation";

const OPTIONS: { mode: UiMode; label: string }[] = [
  { mode: "presentation", label: "Presentation" },
  { mode: "operator", label: "Operator" },
];

export function ModeToggle({ mode, onChange }: { mode: UiMode; onChange: (m: UiMode) => void }) {
  return (
    <div role="group" aria-label="Interface mode" className="inline-flex rounded-full border border-cream/30 p-0.5">
      {OPTIONS.map((o) => (
        <button key={o.mode} type="button" aria-pressed={mode === o.mode} onClick={() => onChange(o.mode)}
          className={`rounded-full px-3 py-1 text-[0.8rem] font-semibold transition-colors ${
            mode === o.mode ? "bg-cream text-forest" : "text-cream/80 hover:text-cream"}`}>
          {o.label}
        </button>
      ))}
    </div>
  );
}
