import type { Headline } from "./types.ts";

// Each number links to its detail; counts and horizon come from the server.
export function HeadlineNumbers({ headline }: { headline: Headline }) {
  const metrics: [string, string | number, string, string, string?][] = [
    ["Open consults", headline.openConsults, "active now", "#consults"],
    ["Past critical", headline.pastCritical, "consults over the limit", "#consults", headline.pastCritical ? "risk" : undefined],
    ["Ready for calls", `${headline.freePhysicians} of ${headline.totalPhysicians}`, "can take a call", "#doctors", "good"],
    ["Signal flags", headline.signalDisagreements, "need checking", "#doctors", headline.signalDisagreements ? "warn" : undefined],
    [`Short in ${headline.forecastHorizonMinutes} min`, headline.shortIn90, "hospitals, now or scheduled", "#command-forecast", headline.shortIn90 ? "risk" : undefined],
    ["Overloaded", headline.overloadedPhysicians, "physicians needing support", "#doctors", headline.overloadedPhysicians ? "warn" : undefined],
    ["Awaiting approval", headline.waitingOnPerson, "offers & escalations", "#command-actions", headline.waitingOnPerson ? "warn" : undefined],
  ];
  return <section className="headline-grid" aria-label="Headline numbers">{metrics.map(([label, value, note, href, tone]) =>
    <a className={`metric-card ${tone ?? ""}`} href={href} key={label}><span>{label}</span><strong>{value}</strong><small>{note} <b aria-hidden="true">→</b></small></a>)}</section>;
}
