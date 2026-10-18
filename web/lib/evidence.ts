/** SAVE EVIDENCE: the backend returns structured JSON; the browser downloads it locally. */

export function evidenceFilename(evidence: Record<string, unknown>, now: Date = new Date()): string {
  const p = (n: number) => String(n).padStart(2, "0");
  const stamp = `${now.getFullYear()}-${p(now.getMonth() + 1)}-${p(now.getDate())}_${p(now.getHours())}${p(now.getMinutes())}${p(now.getSeconds())}`;
  const types = Array.isArray(evidence.violation_types) ? evidence.violation_types.filter((t) => typeof t === "string") : [];
  const verdict = typeof evidence.verdict === "string" ? evidence.verdict : "EVIDENCE";
  const slug = (types.length ? Array.from(new Set(types)).join("_") : verdict).replace(/[^A-Za-z0-9_]/g, "_");
  return `madqaq-evidence_${stamp}_${slug || "EVIDENCE"}.json`;
}

/** True when the export keeps the disclosures the M5 claims rules require. */
export function evidenceIsDisclosed(evidence: Record<string, unknown>): boolean {
  const d = evidence.disclosures as Record<string, unknown> | undefined;
  return evidence.digital_simulated === true && !!d && d.digital_label === "SIMULATED DIGITAL CHANNEL";
}

export function downloadJson(data: unknown, filename: string): void {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
