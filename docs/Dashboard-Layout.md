# Command dashboard layout

The layout follows the live-workload sketch on page 1 of the Challenge 2 Operations Command Center brief, with the connected Detect / Decide / Approve / Act / Update flow from page 2. The reference PDF is in `problem/`; supplied source CSVs remain gitignored.

Command holds only what has no other home, in reading order. Anything with a dedicated page lives there instead, and the headline numbers link to it. Section links scroll to content instead of hiding it behind tabs.

| Section | Visible information and actions |
| --- | --- |
| Headline numbers | Open consults, consults past their Critical threshold, ready-for-calls, signal flags, hospitals short within the server display horizon, overloaded physicians and awaiting approval. Each card links to the Command section or page that explains it. |
| 01 Detect & decide | Server-ranked attention queue and severity filters. Selecting a finding shows its affected site/consult, reason, recommended intervention and approver. Alternatives and exclusions remain available in a disclosure. |
| 02 Forecast | Hospital coverage at least 90 minutes ahead and through nearby shift cliffs; cell detail and Find cover lead to eligibility, proposal and split-shift trap checks. Demand for the last 60 minutes appears below as one tile per hospital, with surges highlighted. |
| 03 Act & close the loop | Two matching cards. Offers in progress shows awaiting-approval and awaiting-reply counts as badges, then one item per offer with its window, hospitals, next step and progress. Completed offers shows accepted and closed counts and links to Audit. |

Moved to dedicated pages:

| Page | Content taken from Command |
| --- | --- |
| Consults | Stage counts (open, documentation, CT/CTA pending, imaging review) and the CT/CTA and imaging-review waiting lists. Selecting a waiting consult scrolls to its row in the lifecycle board. |
| Doctors | Activity counts, the physician activity table (system activity beside self-report, sites, shift totals, shift end), workload and shift-end risk, and signal verification, above the physician board. |
| Audit | Recent activity. Completed offers on Command link here for the full history. |
| Data | Fixed Sevaro reference identity, event-integrity counts, append-only testing and persistent CSV receipts. Empty-stream reset remains a separate explicit action. |

## Data presentation

- Current video/call metrics count physicians in the corresponding system-derived state. Open documentation and imaging metrics count consults. Multiple open consults do not create additional active sessions.
- Physician self-reported status appears beside system activity and routing eligibility. An offline agent is marked as unverified; ringing and cooldown exclusions remain visible.
- Calls and consults are shift totals, not active session counts. Missing call totals display a dash instead of zero. Sites expand to the named credentialed hospitals.
- Stage duration comes from the snapshot's publication time and stage-entry timestamp when both are available; otherwise it uses the published minute count. Total elapsed retains the server's rounded minutes. The browser does not invent an independently advancing replay clock.
- The lifecycle table keeps each consult's own server-provided threshold level, even when a grouped queue item represents several consults. The attention queue retains routing and handoff findings separately. Limits appear only when supplied by the server; documentation flags preserve the cumulative clock since the interaction ended.
- The consult table displays higher priorities first, with consult ID as the stable display tie-breaker. The attention queue retains the server's ranking and order. Routing, eligibility, optimization constraints and objective weights are unchanged.
- Coverage summarizes hospitals below minimum now, at minimum now and with gaps in future intervals. An attention filter includes gaps, unknown/unverified coverage and unreachable sites. Staffing cells retain the server status, show staffed/minimum counts and readable labels, and open a persistent inspection panel. Hospital rows stay visible without vertical clipping; the timeline scrolls horizontally on small screens.
- The intervention section summarizes approval, reply and accepted-offer counts. Offer cards lead with physician, coverage window, hospital chips and the next responsible role; mobile progress runs vertically.
- Offers awaiting approval are labeled as waiting for the clinical lead. Completed offers remain visible after they leave the open-offer list.

## Responsive behavior

The dashboard uses the available canvas width and normal page scrolling. Dense queue and detail panels use viewport-based height limits; tables scroll inside their cards. On narrower screens, columns stack and action buttons remain reachable. No new dependencies are required.

## Validation

Panel, table and link styles are shared across every operations page, so Command, Consults and Doctors use the same cards. Frontend tests cover activity units, snapshot counts, consult ownership, missing call totals, documentation clocks and stage timestamp precision. Browser checks cover desktop/mobile/landscape widths, search, priority filters, section navigation, waiting-consult review, the eligibility/proposal form, lead approval, physician acceptance and completed outcomes. Production TypeScript/Vite build is also checked.

## Merge policy

Joy’s layout and roster timeline are integrated with the audited backend. CSV uploads append and retain their original bytes and receipts; presentation mode refuses event testing. Audio uses authenticated blob playback with cleanup. Schedule groups follow observed online state, and incomplete roster intervals or pending offers never become confirmed capacity.
