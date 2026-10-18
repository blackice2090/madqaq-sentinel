import { PROTOTYPE_NOTE } from "@/lib/disclosures";
import type { Disclosures } from "@/lib/protocol";

/** The single place the privacy, frame-transmission and simulated-channel disclosures are stated. */
export function PrivacyFooter({ d }: { d: Disclosures }) {
  return (
    <footer className="flex flex-wrap items-center justify-between gap-x-6 gap-y-0.5 border-t border-line bg-cream-deep px-6 py-2 short:py-1 text-[0.8rem] leading-snug text-muted">
      <span className="font-semibold text-ink">{d.privacy}</span>
      <span>{d.frames} {d.frames_storage}</span>
      <span>Digital channel is simulated for demonstration. {d.digital_note}</span>
      <span>{PROTOTYPE_NOTE}</span>
    </footer>
  );
}
