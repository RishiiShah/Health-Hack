// The append-only audit trail, newest first: time, actor, action and detail in columns.
import { PageHead } from "../ui/Layout.tsx";
import { unavailableText, useApi } from "./hooks.ts";
import { clockTimeSeconds } from "./time.ts";
import type { AuditEntry } from "./types.ts";
import "./act.css";

export function AuditPage({ reloadKey }: { reloadKey: unknown }) {
  const { data, error } = useApi<{ items: AuditEntry[] }>("/audit", reloadKey);
  return <>
    <PageHead kicker="Record" title="Audit" note="Every recommendation, proposal, approval and reply, as the server recorded it." />
    <section className="panel audit-list">
      {error && !data ? <p className="unavailable">{unavailableText(error, "GET /audit")}</p>
        : !data?.items.length ? <p className="unavailable">Nothing recorded yet.</p>
          : data.items.slice().reverse().map((row, i) => <div key={i}><span className="mono muted">{clockTimeSeconds(row.at)}</span><b>{row.actor}</b><strong>{row.action}</strong><span>{row.detail}</span></div>)}
    </section>
  </>;
}
