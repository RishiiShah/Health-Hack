import type { Headline } from "./types.ts";

export function HeadlineNumbers({ headline }: { headline: Headline }) {
  const metrics = [["Open consults", headline.openConsults, "active now"], ["Critical alerts", headline.pastCritical, "highest-priority findings"], ["Ready for calls", `${headline.freePhysicians} of ${headline.totalPhysicians}`, "can take a call"], ["Signal flags", headline.signalDisagreements, "need checking"], ["Forecast gaps", headline.shortIn90, "hard gaps in next 90 min"], ["Awaiting approval", headline.waitingOnPerson, "offers & escalations"]];
  return <section className="headline-grid" aria-label="Headline numbers">{metrics.map(([label, value, note]) => <article className="metric-card" key={String(label)}><span>{label}</span><strong>{value}</strong><small>{note}</small></article>)}</section>;
}
