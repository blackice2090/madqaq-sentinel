import { Camera, CameraOff, LoaderCircle, ShieldCheck, Wifi, WifiOff } from "lucide-react";

import type { StatusView } from "@/lib/connection";
import type { VisionStatus } from "@/lib/protocol";

function Pill({ ok, label, icon }: { ok: boolean; label: string; icon: React.ReactNode }) {
  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm font-bold tracking-wide ${
        ok ? "border-cream/60 bg-cream text-forest" : "border-ember bg-forest-deep text-cream"}`}
      role="status"
    >
      {icon}
      {label}
    </span>
  );
}

export function Header({ status, vision, engineVersion }: {
  status: StatusView; vision: VisionStatus | null; engineVersion: string | null;
}) {
  const connected = status.backendLabel === "BACKEND CONNECTED";
  const connecting = status.backendLabel === "CONNECTING";
  return (
    <header className="flex items-center justify-between gap-6 bg-forest px-6 py-3 text-cream">
      <div className="flex items-center gap-4">
        <ShieldCheck aria-hidden className="size-9 text-ember" />
        <div>
          <h1 className="text-2xl font-extrabold tracking-[0.18em]">MADQAQ SENTINEL</h1>
          <p className="text-sm font-medium tracking-wide text-cream/80">Dual-Channel Procedure Integrity</p>
        </div>
      </div>
      <div className="flex flex-wrap items-center justify-end gap-2">
        {vision === "loading" && (
          <Pill ok={false} label="LOADING DETECTOR" icon={<LoaderCircle aria-hidden className="size-4 animate-spin" />} />
        )}
        {vision === "unavailable" && <Pill ok={false} label="DETECTOR UNAVAILABLE" icon={<CameraOff aria-hidden className="size-4" />} />}
        <Pill
          ok={status.cameraLabel === "CAMERA ACTIVE"}
          label={status.cameraLabel}
          icon={status.cameraLabel === "CAMERA ACTIVE" ? <Camera aria-hidden className="size-4" /> : <CameraOff aria-hidden className="size-4" />}
        />
        <Pill
          ok={connected}
          label={status.backendLabel}
          icon={connected ? <Wifi aria-hidden className="size-4" />
            : connecting ? <LoaderCircle aria-hidden className="size-4 animate-spin" /> : <WifiOff aria-hidden className="size-4" />}
        />
        {engineVersion && <span className="hidden text-xs text-cream/60 xl:inline">engine {engineVersion}</span>}
      </div>
    </header>
  );
}
