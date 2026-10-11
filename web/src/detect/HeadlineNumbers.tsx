import type { Headline } from "./types.ts";

export function HeadlineNumbers({ headline }: { headline: Headline }) {
  const metrics = [["Open consults", headline.openConsults, "active now"], ["Past critical", headline.pastCritical, "over the limit"], ["Free", `${headline.freePhysicians} of ${headline.totalPhysicians}`, "can take a call"], ["Signals disagree", headline.signalDisagreements, "need checking"], [`Short in ${headline.forecastHorizonMinutes} min`, headline.shortIn90, "hospitals, now or scheduled"], ["Overloaded", headline.overloadedPhysicians, "physicians needing support"], ["Waiting on a person", headline.waitingOnPerson, "needs action"]];
  return <section className="headline-grid" aria-label="Headline numbers">{metrics.map(([label, value, note]) => <article className="metric-card" key={String(label)}><span>{label}</span><strong>{value}</strong><small>{note}</small></article>)}</section>;
}
