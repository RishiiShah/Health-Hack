import type { Headline } from "./types.ts";

// Each number links to where its detail lives: a Command section or a dedicated page.
export function HeadlineNumbers({ headline }: { headline: Headline }) {
  const metrics: [string, string | number, string, string, string?][] = [
    ["Open consults", headline.openConsults, "active now", "#consults"],
    ["Critical alerts", headline.pastCritical, "highest-priority findings", "#command-attention", headline.pastCritical ? "risk" : undefined],
    ["Ready for calls", `${headline.freePhysicians} of ${headline.totalPhysicians}`, "can take a call", "#doctors", "good"],
    ["Signal flags", headline.signalDisagreements, "need checking", "#doctors", headline.signalDisagreements ? "warn" : undefined],
    ["Forecast gaps", headline.shortIn90, "hard gaps in next 90 min", "#command-forecast", headline.shortIn90 ? "risk" : undefined],
    ["Awaiting approval", headline.waitingOnPerson, "offers & escalations", "#command-actions", headline.waitingOnPerson ? "warn" : undefined],
  ];
  return <section className="headline-grid" aria-label="Headline numbers">{metrics.map(([label, value, note, href, tone]) =>
    <a className={`metric-card ${tone ?? ""}`} href={href} key={label}><span>{label}</span><strong>{value}</strong><small>{note} <b aria-hidden="true">→</b></small></a>)}</section>;
}
