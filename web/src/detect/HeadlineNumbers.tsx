import type { DetectSnapshot } from "./types.ts";

export function HeadlineNumbers({ data }: { data: DetectSnapshot }) {
  const metrics = [["Open consults", data.headline.openConsults, "active now"], ["Past critical", data.headline.pastCritical, "since 18:20"], ["Free", `${data.headline.freePhysicians} of ${data.headline.totalPhysicians}`, "can take a call"], ["Signals disagree", data.headline.signalDisagreements, "need checking"], ["Short in 90 min", data.headline.shortIn90, "coverage gap"], ["Waiting on person", data.headline.waitingOnPerson, "needs action"]];
  return <section className="headline-grid" aria-label="Headline numbers">{metrics.map(([label, value, note]) => <article className="metric-card" key={String(label)}><span>{label}</span><strong>{value}</strong><small>{note}</small></article>)}</section>;
}
