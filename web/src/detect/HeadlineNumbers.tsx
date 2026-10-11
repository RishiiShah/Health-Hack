import { Chip, Kpi } from "../ui/Kpi.tsx";
import type { Headline } from "./types.ts";

// Four numbers that decide the next move, then the rest as compact links. Counts and horizon come from the server.
export function HeadlineNumbers({ headline }: { headline: Headline }) {
  return <section aria-label="Headline numbers">
    <div className="kpi-row">
      <Kpi order={0} label="Open consults" value={headline.openConsults} note="active now" href="#consults" />
      <Kpi order={1} label="Past critical" value={headline.pastCritical} note="over the stage limit" href="#consults" tone={headline.pastCritical ? "risk" : undefined} />
      <Kpi order={2} label="Ready for calls" value={headline.freePhysicians} of={headline.totalPhysicians} note="physicians free" href="#doctors" tone={headline.freePhysicians ? "good" : "risk"} />
      <Kpi order={3} label={`Short in ${headline.forecastHorizonMinutes} min`} value={headline.shortIn90} note="hospitals, now or scheduled" href="#coverage" tone={headline.shortIn90 ? "risk" : undefined} />
    </div>
    <div className="chip-row">
      <Chip order={4} label="Awaiting approval" value={headline.waitingOnPerson} href="#dispatch" />
      <Chip order={5} label="Signal flags" value={headline.signalDisagreements} href="#doctors" />
      <Chip order={6} label="Overloaded" value={headline.overloadedPhysicians} href="#doctors" />
    </div>
  </section>;
}
