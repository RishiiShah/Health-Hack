import { unavailableText, useApi } from "./hooks.ts";
import { clockTimeSeconds } from "./time.ts";
import type { AuditEntry } from "./types.ts";
import "./act.css";

export function AuditLog({ gapId, reloadKey }: { gapId: string; reloadKey: unknown }) {
  const { data, error } = useApi<{ items: AuditEntry[] }>(`/audit?gap_id=${encodeURIComponent(gapId)}`, reloadKey);
  return (
    <section>
      <h2>Audit log</h2>
      {error && !data ? (
        <p className="unavailable">{unavailableText(error, "GET /audit")}</p>
      ) : !data?.items.length ? (
        <p className="unavailable">Nothing recorded for this gap yet.</p>
      ) : (
        <ol className="audit">
          {data.items.map((a, i) => (
            <li key={i}>
              <time>{clockTimeSeconds(a.at)}</time>
              <span><b>{a.actor}</b> · {a.action}{a.detail && <span className="muted"> · {a.detail}</span>}</span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
