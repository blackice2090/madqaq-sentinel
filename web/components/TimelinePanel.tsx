import { Camera, Database } from "lucide-react";

import { TIMELINE_ROWS } from "@/lib/config";
import { channelLabel, eventLabel, formatConfidence, formatTime } from "@/lib/format";
import type { TimelineRow } from "@/lib/protocol";

import { Panel } from "./Panel";

export function TimelinePanel({ rows, stale }: { rows: TimelineRow[]; stale: boolean }) {
  const latest = rows.slice(-TIMELINE_ROWS).reverse();
  return (
    <Panel title="Evidence Timeline" aside={<span className="text-xs text-muted">latest {TIMELINE_ROWS}, newest first</span>}>
      {latest.length === 0 ? (
        <p className="text-sm italic text-muted">No evidence events yet.</p>
      ) : (
        <table className={`w-full text-left text-sm ${stale ? "opacity-50" : ""}`}>
          <thead className="text-xs uppercase tracking-wider text-muted">
            <tr><th className="py-1 font-bold">Time</th><th className="font-bold">Channel</th><th className="font-bold">Step</th>
              <th className="font-bold">Event</th><th className="text-right font-bold">Confidence</th></tr>
          </thead>
          <tbody className="divide-y divide-line">
            {latest.map((r) => (
              <tr key={r.event_id}>
                <td className="py-1 font-mono">{formatTime(r.timestamp)}</td>
                <td>
                  <span className="inline-flex items-center gap-1.5 font-semibold">
                    {r.channel === "PHYSICAL" ? <Camera aria-hidden className="size-4 text-forest" /> : <Database aria-hidden className="size-4 text-ember-deep" />}
                    {channelLabel(r.channel, r.simulated)}
                  </span>
                </td>
                <td><span className="font-mono font-extrabold">{r.step_id}</span> {r.step_name}</td>
                <td className="font-semibold">{eventLabel(r.event_type)}</td>
                <td className="text-right font-mono">{formatConfidence(r.confidence)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Panel>
  );
}
