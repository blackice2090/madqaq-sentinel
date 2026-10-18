import { TIMELINE_ROWS } from "@/lib/config";
import { eventLabel, formatConfidence, formatTime } from "@/lib/format";
import type { TimelineRow } from "@/lib/protocol";

export function EvidenceTimeline({ rows, stale }: { rows: TimelineRow[]; stale: boolean }) {
  const latest = rows.slice(-TIMELINE_ROWS).reverse();
  return (
    <section aria-label="Evidence timeline" className="flex min-h-0 flex-1 flex-col rounded-xl border border-line bg-white px-4 py-3 short:py-2">
      <h2 className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">
        Evidence timeline <span className="ml-2 font-normal normal-case tracking-normal">newest first</span>
      </h2>
      {latest.length === 0 ? (
        <p className="mt-2 text-sm text-muted">No evidence events yet.</p>
      ) : (
        <div className="mt-1 min-h-0 overflow-y-auto">
          <table className={`w-full text-left text-sm transition-opacity ${stale ? "opacity-50" : ""}`}>
            <thead className="sticky top-0 bg-white text-xs uppercase tracking-wider text-muted">
              <tr>
                <th className="py-1 pr-3 font-semibold">Time</th><th className="pr-3 font-semibold">Channel</th>
                <th className="pr-3 font-semibold">Step</th><th className="pr-3 font-semibold">Event</th>
                <th className="text-right font-semibold">Confidence</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line/60">
              {latest.map((r) => (
                <tr key={r.event_id}>
                  <td className="py-1 short:py-0 pr-3 font-mono">{formatTime(r.timestamp)}</td>
                  <td className={`pr-3 font-semibold whitespace-nowrap ${r.channel === "DIGITAL" ? "text-ember-deep" : "text-forest"}`}>
                    {r.channel === "DIGITAL" && r.simulated ? "DIGITAL · SIMULATED" : r.channel}
                  </td>
                  <td className="pr-3"><span className="font-mono font-extrabold">{r.step_id}</span> {r.step_name}</td>
                  <td className="pr-3 font-medium">{eventLabel(r.event_type)}</td>
                  <td className="text-right font-mono">{formatConfidence(r.confidence)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
