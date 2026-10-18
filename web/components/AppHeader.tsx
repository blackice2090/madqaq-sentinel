import { ShieldCheck } from "lucide-react";

import type { StatusView } from "@/lib/connection";
import type { UiMode } from "@/lib/presentation";

import { ModeToggle } from "./ModeToggle";
import { StatusPill } from "./StatusPill";

export function AppHeader({ status, mode, onMode, analysis, engineVersion }: {
  status: StatusView; mode: UiMode; onMode: (m: UiMode) => void;
  analysis: { label: string; healthy: boolean }; engineVersion: string | null;
}) {
  return (
    <header className="flex items-center justify-between gap-6 bg-forest px-6 py-2.5 text-cream">
      <div className="flex items-center gap-3">
        <ShieldCheck aria-hidden className="size-8 text-ember" />
        <div>
          <h1 className="text-xl font-extrabold leading-tight tracking-[0.16em]">MADQAQ SENTINEL</h1>
          <p className="text-sm leading-tight text-cream/75">Dual-Channel Procedure Integrity</p>
        </div>
      </div>
      <div className="flex flex-wrap items-center justify-end gap-2">
        <StatusPill ok={analysis.healthy} label={analysis.label} />
        <StatusPill ok={status.cameraLabel === "CAMERA ACTIVE"} label={status.cameraLabel} />
        <StatusPill ok={status.backendLabel === "BACKEND CONNECTED"} label={status.backendLabel} />
        <ModeToggle mode={mode} onChange={onMode} />
        {engineVersion && <span className="hidden text-xs text-cream/50 2xl:inline">engine {engineVersion}</span>}
      </div>
    </header>
  );
}
