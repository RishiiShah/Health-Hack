# Command dashboard layout

The layout follows the live-workload sketch on page 1 of the Challenge 2 Operations Command Center brief, with the connected Detect / Decide / Approve / Act / Update flow from page 2. The reference PDF stays outside the repository.

All four sections remain on one Command page. Section links scroll to content instead of hiding it behind tabs.

| Section | Visible information and actions |
| --- | --- |
| Live workload | Video and call activity counts, open documentation, CT/CTA and imaging review waits; physician activity, credentialed sites, call/consult shift totals, open docs and shift-end times. Consult ownership and lifecycle stay on the dedicated Consults page, with search and priority filters. |
| Detect & decide | Server-ranked attention queue and severity filters. Selecting a finding shows its affected site/consult, reason, recommended intervention and approver. Alternatives and exclusions remain available in a disclosure. |
| Coverage forecast | Hospital coverage through the next 90 minutes; cell detail and Find cover lead to eligibility, proposal and split-shift trap checks. Demand and shift-end risk remain below the grid. |
| Act & close the loop | Explicit human approval step, open-offer progress, completed offer outcomes and recent audit events. Event-integrity counts link to Data and live event testing. |

## Data presentation

- Current video/call metrics count physicians in the corresponding system-derived state. Open documentation and imaging metrics count consults. Multiple open consults do not create additional active sessions.
- Physician self-reported status appears beside system activity and routing eligibility. An offline agent is marked as unverified; ringing and cooldown exclusions remain visible.
- Calls and consults are shift totals, not active session counts. Missing call totals display a dash instead of zero. Sites expand to the named credentialed hospitals.
- Stage duration comes from the snapshot's publication time and stage-entry timestamp when both are available; otherwise it uses the published minute count. Total elapsed retains the server's rounded minutes. The browser does not invent an independently advancing replay clock.
- Consult priority is supplied by the ranked queue and can include routing or handoff risks. It is distinct from a stage threshold. Limits appear only when supplied by the server; documentation flags preserve the cumulative clock since the interaction ended.
- The consult table displays higher priorities first, with consult ID as the stable display tie-breaker. The attention queue retains the server's ranking and order. Routing, eligibility, optimization constraints and objective weights are unchanged.
- Coverage summarizes hospitals below minimum now, at minimum now and with gaps in future intervals. An attention filter includes gaps, unknown/unverified coverage and unreachable sites. Staffing cells retain the server status, show staffed/minimum counts and readable labels, and open a persistent inspection panel. Hospital rows stay visible without vertical clipping; the timeline scrolls horizontally on small screens.
- The intervention section summarizes approval, reply and accepted-offer counts. Offer cards lead with physician, coverage window, hospital chips and the next responsible role; mobile progress runs vertically. Recent audit entries resolve known physician/hospital IDs and convert timestamp text to Eastern time, while original records and the full audit remain accessible.
- Offers awaiting approval are labeled as waiting for the clinical lead. Completed offers remain visible after they leave the open-offer list.

## Responsive behavior

The dashboard uses the available canvas width and normal page scrolling. Dense queue and detail panels use viewport-based height limits; tables scroll inside their cards. On narrower screens, columns stack and action buttons remain reachable. No new dependencies are required.

## Validation

Frontend tests cover activity units, snapshot counts, consult ownership, missing call totals, documentation clocks and stage timestamp precision. Browser checks cover desktop/mobile/landscape widths, search, priority filters, section navigation, waiting-consult review, the eligibility/proposal form, lead approval, physician acceptance and completed outcomes. Production TypeScript/Vite build is also checked.
