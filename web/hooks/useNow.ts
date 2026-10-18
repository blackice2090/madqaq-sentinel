"use client";

import { useEffect, useState } from "react";

/** Wall-clock milliseconds, refreshed every `periodMs` (drives staleness checks). */
export function useNow(periodMs: number): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), periodMs);
    return () => window.clearInterval(t);
  }, [periodMs]);
  return now;
}
