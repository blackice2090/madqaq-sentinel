import { CircleCheck, CircleDashed, CircleQuestionMark, CircleX, CloudOff } from "lucide-react";

import type { Tone } from "@/lib/format";

/** Status is always icon + word, never colour alone. */
export function ToneIcon({ tone, className = "size-5" }: { tone: Tone; className?: string }) {
  switch (tone) {
    case "ok": return <CircleCheck aria-hidden className={`${className} text-forest`} />;
    case "violation": return <CircleX aria-hidden className={`${className} text-ember-deep`} />;
    case "uncertain": return <CircleQuestionMark aria-hidden className={`${className} text-muted`} />;
    case "stale": return <CloudOff aria-hidden className={`${className} text-muted`} />;
    default: return <CircleDashed aria-hidden className={`${className} text-muted`} />;
  }
}

export const toneText: Record<Tone, string> = {
  ok: "text-forest",
  violation: "text-ember-deep",
  uncertain: "text-muted",
  neutral: "text-muted",
  stale: "text-muted",
};
