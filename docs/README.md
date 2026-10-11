# Current implementation and document authority

Use this index to distinguish the current release contract from planning and
historical handoffs. Backend decisions remain deterministic; clients display
the server's findings, candidates, permissions and outcomes.

| Question | Current authority |
| --- | --- |
| Challenge requirements, gates and acceptance cases | [PRD v2](Sevaro%20Command%20Center%20PRD%20v2.md); source brief and handbook remain requirements |
| Implemented rule assumptions, capacities and stable tie-breakers | [Decision Engine](Decision-Engine.md), linked tests and `backend/app/` |
| Implemented endpoints, roles and dependencies | [Boundaries and Contracts](00-Boundaries-and-Contracts.md), `/openapi.json`, API tests |
| Current mobile adapter versus the larger design contract | [Mobile contract scope](Mobile-App-Contract.md), [mobile README](../mobile/README.md) |
| Runtime, production database and startup recovery | [Deployment](Deployment.md), [Reference Data](Reference-Data.md) |
| Completed review fixes and verification limits | [E2E audit and handoffs](E2E-Audit-2026-10-11.md), [Gap fixes](Decision-Engine-Gap-Fixes.md), [Judge Test Plan](Judge-Test-Plan.md), [CSV audit](CSV-Ingestion-Audit.md) |

The backend uses **Python 3.14.7**, FastAPI, one Uvicorn worker and PostgreSQL.
Production RDS is provisioned in **us-west-2**; a Render application deployment
has not been verified. The original Virginia/us-east-1 hosting templates still
need region alignment before deployment. There is no SQLite production store.

Web uses React, Vite and TypeScript; the existing landing page also uses Tailwind.
ECharts is not installed. The current web snapshot client uses serialized REST
polling; `/ws` exists on the backend but is not the web client's transport.
Password accounts determine roles; no login role selector changes permission.
`CC_AUTH_CONFIG` overrides environment account configuration. Fixed role tokens
and signed physician tokens are separate optional demo/API access mechanisms.

The implemented Act loop supports one physician per offer, lead approval,
sequential fallback, replies, expiry and durable audit. It is implemented scope,
even where historical task schedules call it stretch. It records recommended
reassignments; it does not drive Sevaro's production router. Mobile live mode
adapts these existing workflows. Broadcasts, mobile schedule screens, preference
editing, release and stored read receipts remain unimplemented design features.

## Approved decision policies

The approved G15 attention policy is lexicographic: severity, horizon,
ownerless, stroke, repeat contacts, age, affected count, stable ID. The display
`score` is ordinal. Severity is a hard priority; additive bonuses cannot move a
Warning above a Critical. Rishi approved retaining this behavior after reviewing
the alternatives. The PRD and Decision Engine §5.5 now specify the same key.
This policy choice is not a measured speed improvement or an optimization proof.

PRD G18's shorthand candidate order is expanded by the implemented gap-minute,
arrival, declines, hours, weekly-offer and ID key. G19 includes explicit seeds,
peer tolerance and multiple demand scenarios in Decision Engine §5.3–5.4.
Rishi approved A41's joiner-versus-peer load bound for **baseline demand only**.
Site restrictions, non-worsening gap wait and peer-load tolerance apply to every
scenario. Fallback physicians remain alternatives, not reserved capacity;
coordinators choose one assignment and refresh before acting on another item.
Primary recommendations retain the existing reservations.

The displayed forecast extends at least 90 minutes through the last complete
shift boundary within 120 minutes, with exact boundary steps. This resolves the
18:20 → 20:00 display requirement; the routing simulator retains its documented
90-minute horizon.

## Judging and proposed weekend assumptions

The latest [E2E audit](E2E-Audit-2026-10-11.md) verified real CSV uploads, role
permissions, the offer/arrival loop and server replacement on disposable
localhost PostgreSQL. Verification: 383 backend, 58 web and 149 mobile tests,
web/Flutter builds and clean Flutter analysis. Its three handoffs separate
delivered behavior from hosted, device, audio and weekend-scenario work.

[Judging review and weekend scenarios](Judging-and-Weekend-Assumptions.md) maps the supplied rubric to evidence and gaps. It proposes a separate read-only weekday-proxy weekend scenario with explicit provenance and acceptance tests. This is a design proposal; official weekend baselines and live surge status remain unknown.

## Historical and planned documents

`Command Center Backend Scaffold.md`, `Backend Scaffold Review.md` and
`P2-Backend.md` retain historical architecture, measurements and ownership
handoffs. Their SQLite/Python/test-count statements are historical evidence,
not current runtime instructions. Web and mobile owner task lists describe
planned acceptance targets; their status banners identify current delivery
differences. Use the live mobile adapter scope ahead of v1.1 design-only routes.

`Synthetic-Data-Krish.md` records the generator specification and delivery
scope. `scripts/synth` now generates five reproducible rehearsal datasets, all
20 event types, authored expected snapshots, DST and live append cases, R1–R8
rejections, and 10×/100× workloads. CI verifies the standard-library generator
and public backend replay parity. See [generator instructions](../scripts/synth/README.md).
Generated data, protected source/answer keys, databases and credentials stay
uncommitted. The live rehearsal uses an independent namespace in a disposable
database; it does not modify or extend the official files.

The release checkout now contains backend, web and mobile source together.
Run backend tests, web tests/build, and Flutter analysis/tests/web builds from
their respective directories. CI runs the same public source checks. Private
four-pack checks require the locally supplied `test_data/`; skipped private
checks must not be reported as passed. Connected-device and hosted-browser
rehearsals remain separate from compiling a Flutter web bundle.
