# Judging review and proposed weekend scenarios

Status: design proposal, 2026-10-11. Weekend assumptions are not implemented or enabled. The live decision policy remains in [Decision Engine](Decision-Engine.md), and the fixed source policy remains in [Reference Data](Reference-Data.md).

## Reading the supplied judging rubric

The supplied image scores five categories from 1 to 5. It is an evaluation rubric, not evidence that the judges permit new reference data or require a trained predictor. No score is assigned here; the demo and evidence must establish each claim.

| Criterion | Evidence we can demonstrate | Gap or strongest next step |
| --- | --- | --- |
| Innovation & Creativity | Explainable Detect–Decide–Act loop; compare no intervention, unrestricted joiner and guarded joiner; show why the intuitive staffing fix can harm another hospital | Demonstrate the counterfactual and constraints with one understandable case. Do not claim industry novelty without a comparison |
| Technical Implementation | Deterministic replay, immutable reference hashes, atomic CSV receipts/clock, persisted offers and audits; latest verification: 378 backend and 58 web tests plus build and browser checks | Deploy and verify the hosted service, source fingerprint, ingestion and restart persistence |
| Healthcare Impact | Show unassigned Stroke work, overdue contact, unfinished documentation at shift end, and credentialed coverage; the simulator checks waiting and peer harm | Report simulated patient waiting/coverage before and after, with assumptions visible. Clinical outcome improvement has not been validated |
| Presentation & Demonstration | Upload unseen compatible events; show unchanged reference data, updated queue/surge, coverage horizon and offer lifecycle | Rehearse a short connected story. Explicitly distinguish observed facts, expected demand, hypothetical scenarios and unknowns |
| Feasibility & Scalability | Persistent PostgreSQL/RDS, authenticated roles, repeatable deployment and stable replay contracts | Verify Render deployment and latency with the deployed database. Current architecture supports one process/instance; horizontal replicas are not yet supported |

A weekend scenario can improve explanation and robustness evidence. It does not by itself establish empirical accuracy, clinical impact, cloud readiness, or scalability.

## Source facts

The immutable official kit contains 288 baseline source rows: 12 hospitals × 24 ET hours, with `dow_type=weekday` and `weeks_sampled=12`. Loading expands these to 1,440 lookup entries for Monday–Friday. These are repeated weekday aggregates, not five independently sampled daily histories. No weekend baseline is supplied. Mean and p90 aggregates cannot reconstruct the underlying counts or establish a calibrated weekend surge probability.

The problem's demand spike rule compares distinct trailing-60-minute consults strictly above that hospital/hour's p90, increasing the staffing requirement by one. Forward coverage must consider shift ends and demand for at least 90 minutes. Neither requirement supplies a weekend demand multiplier.

## Recommended assumption

Offer a separate, explicitly selected **Weekend planning scenario — assumed from weekday baseline**. Keep official/live weekend surge status unknown. Keep the six source files, hashes and reference revision unchanged. Scenario inputs/results must be separate from operational offers, routing and approvals.

For each hospital and ET hour with a valid official weekday row:

- Proxy expected arrival rate = that row's `mean_consults`.
- Proxy busy-hour threshold = that row's `p90_consults`, labeled an **assumed threshold**, not a measured weekend p90.
- Any missing row stays unknown; do not substitute a national average or another hospital's values.
- Start with a 1.0× weekday-rate planning case. Compare a 1.5× arrival-rate stress case, leaving the assumed busy threshold unchanged. The 1.5 setting is an illustrative test parameter, not an estimate of weekend demand. More stress does not justify inflating the threshold and hiding overload.
- Keep live observed counts exact. Simulated arrivals stay inside the scenario and never enter the event log or acquire patient identifiers.

There is no evidence for reducing weekend demand because the day is Saturday/Sunday. The proposed proxy is transparent and reproducible, but is not guaranteed to be conservative: real weekends could exceed both illustrative rates. Show sensitivity rather than claim statistical confidence.

### What the administrator would see

The official Data section continues to show “No baseline supplied for Sat, Sun.” A separate scenario control identifies its source fingerprint, versioned assumption, date/time, multiplier and horizon. Results show both “Official baseline: unknown” and “Scenario: weekday proxy,” plus expected arrivals, the assumed busy threshold, any hypothetical coverage gaps and their causes. Exports preserve those labels and inputs. No automatic lead approval or physician contact follows a hypothetical result.

The same scenario inputs, event prefix, schedule inputs, algorithm version and clock must replay to the same result. Scenario history is distinct from CSV upload history and official reference provenance.

## Demand does not establish staffing

The supplied kit's dated shifts and scheduled starts describe the March 17 rehearsal. Do not move them to a Saturday merely by changing the date. A weekend capacity scenario needs explicitly dated shift windows, credentials, physician availability and applicable staffing requirements; missing intervals remain unknown. Accepted-offer and observed-arrival rules still apply. Demand-only results can be shown when staffing inputs are absent, but they cannot establish that weekend coverage is sufficient.

This is why the first implementation should be a read-only scenario view, not a global fallback inside `OpsRefs.mean/p90` that silently changes authoritative decisions.

## TDD acceptance before implementation

1. Selecting or replaying a scenario never changes source hashes, reference revision, official baseline inventory, event log or live decisions.
2. A known hospital/hour uses the exact supplied weekday aggregate; another hospital's row cannot fill a missing value. Official weekend mean/p90 remain null.
3. Partial-hour, midnight, weekend boundary, ET and DST cases integrate elapsed time correctly; missing any required hour makes the total unknown.
4. Observed repeat contacts/duplicate CSV rows do not add distinct demand. The assumed threshold uses strict `>`; equality is not a spike.
5. The 1.5× scenario changes hypothetical arrival demand only, not source p90, observed counts or real queue thresholds.
6. Missing weekend shift windows are visibly unknown. The Tuesday schedule is never counted as confirmed weekend capacity.
7. Credentials, hospital restrictions, waiting constraints and peer-harm limits hold in every simulated scenario. Recommendations retain deterministic tie-breakers.
8. UI, export, restart/replay and audit all retain the assumption label, settings and source fingerprint. Scenario outcomes cannot send operational offers or reassignments.

## Suggested demonstration

Show an unseen weekday CSV first: reference fingerprint stable, observed demand changes, p90 spike detected, an exact upcoming shift cliff, and an approved intervention's lifecycle. Then open the proposed weekend scenario: the official baseline remains unknown, the planning assumption is visible, and additional demand/schedule uncertainty changes the hypothetical results. Present this as handling incomplete inputs responsibly, not as a validated weekend predictor.
