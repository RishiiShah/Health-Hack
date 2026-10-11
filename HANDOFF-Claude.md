# Claude handoff — Sevaro Command Center

Updated October 11, 2026. Repository: `/Users/rishi/Desktop/CLG/Health Hack`.
Branch: `rishi`. Base commit: `467905c` (`Document E2E verification and engineering handoffs`). The six fixes and this handoff are committed together on top of that base; use `git log -1` for the resulting commit ID.

## Start here

Read `AGENTS.md`, `CLAUDE.md` and `docs/README.md`, then:

- Original challenge: `problem/Sevaro_Rutgers_Health_Hack_Challenge_2_Operations_Command_Center.pdf` and its handbook.
- Requirements and acceptance gates: `docs/Sevaro Command Center PRD v2.md`.
- Implemented rules, assumptions and tie-breakers: `docs/Decision-Engine.md`.
- Current API and role boundaries: `docs/00-Boundaries-and-Contracts.md`.
- Completed fixes: `docs/Decision-Engine-Gap-Fixes.md`, especially the final "Devil's advocate review fixes" section.
- Earlier end-to-end evidence and remaining delivery work: `docs/E2E-Audit-2026-10-11.md`.

`HANDOFF-codex.md` is an older, untracked handoff. Its commit, test counts and several open tasks are superseded. The latest fixes are committed locally and have not been pushed. Preserve the existing handoff. Make further commits or push only when requested.

## What is built

The implemented scope is the challenge's Detect–Decide–Act operations loop: replay timestamped events, derive consult/physician state, detect delays and coverage gaps, recommend deterministic interventions, evaluate off-shift candidates, simulate the split-shift routing trap, and support lead-approved offers, physician replies, expiry, sequential fallback and durable audit.

Backend: Python 3.14.7, FastAPI, PostgreSQL, injected clocks and deterministic replay. Web: React/Vite/TypeScript. Flutter mobile is integrated and adapts the existing backend workflows. Clients display server decisions and permissions. Recommended reassignments are recorded; integration with Sevaro's production router is outside the delivered implementation.

Approved policies to preserve:

- G15 uses lexicographic priority: severity, horizon, ownerless, stroke, repeat contact, age, affected count, stable ID. Display scores are ordinal.
- A41's joiner-versus-busiest-peer load bound applies to baseline demand. Hospital restriction, non-worsening gap wait and peer-load tolerance apply to every modeled scenario.
- Fallback physicians are unreserved alternatives. Primary recommendations retain reservations. Coordinators choose an assignment and refresh before acting on another recommendation.

## Latest work: six review findings implemented

The user requested a devil's advocate review against the problem statement, then explicitly authorized implementing all six findings, including the affected backend, web and mobile files.

1. **Rest after accepted shifts:** `backend/app/decide/eligibility.py` uses the latest known preceding shift end from roster, reference schedules and accepted obligations. Active accepted shifts also prevent an off-shift offer. Future obligations retain overlap checks. Exactly ten hours passes; less fails.
2. **Unapproved offer disclosure:** `backend/app/act/offers.py` centralizes physician read filtering. List/detail/media expose only owned offers with `sent_at`; unsent proposals, rejections and cancellations are hidden. Operations roles retain review access. Sent offers remain visible through their terminal outcomes.
3. **Stale offline camera:** `backend/app/engine/physician.py` trusts camera activity only while the desktop agent is online. Heartbeat loss yields available/unverified unless a real call/video, TU status, ringing or cooldown blocks routing. Fresh camera evidence restores online classification.
4. **Late acceptance eligibility:** `backend/app/act/offers.py` rechecks all rules at the reply clock. Expected readiness must leave two useful hours. The current sent offer counts once toward the weekly cap. An invalid acceptance returns audited 409, adds no coverage and leaves the offer SENT until normal expiry/withdrawal. The third weekly offer can still be accepted.
5. **Incomplete trap demand:** `routing_sim.py` unions missing hospitals across scenarios and prevents a passing verdict when demand is incomplete. `interventions.py` and `service.py` expose `unknown_demand` and explicit partial-model reasons. Web shows Unknown; mobile surfaces the missing-evidence reason rather than pass/fail. Partial runs remain inspectable.
6. **Incorrect proposal window:** web `OfferForm.tsx` uses `candidate.window` and its hospital set. New `offerWindow.ts` preserves evaluated duration during minute rounding and endpoint dates across midnight. `GapPanel.tsx` resets the form when the selected candidate/window changes. Edits are revalidated by the backend.

Regressions were added in `test_offers.py`, `test_p2.py`, `test_routing_sim.py`, `test_api_core.py`, `web/src/act/offerWindow.test.ts` and the mobile adapter test. Shared synthetic backend/mobile JSON fixtures were updated together and match exactly. No dependencies or optimization policies changed.

## Verified locally after the fixes

- Backend: **410 passed**, including local protected-pack checks. One existing Starlette/httpx deprecation warning.
- Web: **62 passed** and production build passed.
- Mobile: **149 passed**, static analysis clean. The eight adapter tests also passed after the final fixture update.
- `git diff --check` passed.

Commands:

```sh
# From backend/
.venv/bin/python -m pytest -q

# From web/, run separately
npm test
npm run build

# From mobile/, run separately
/private/tmp/health-hack-flutter/bin/flutter analyze --no-pub
/private/tmp/health-hack-flutter/bin/flutter test --no-pub
```

Backend fixtures create disposable databases on local PostgreSQL at port 5432. Backend tests and Flutter tests require local socket access; sandboxed runs needed escalation. The temporary Flutter SDK path is machine-local. The current changes were not verified on a hosted application or physical device.

## Constraints and remaining work

Use standard-library tools first. Keep Python 3.14.7 aligned across CI, Docker and runtime docs. Routing/operations use deterministic rules, explicit capacities and stable tie-breakers; no AI/ML or provider dependencies for decisions. Inject time into rule logic. Notification content excludes patient/consult details.

Preserve source/answer-key separation. Generated data, protected CSVs, environments, databases and secrets stay uncommitted. Do not edit `web/src/api/types.gen.ts` or supplied `data/*.csv`. Holdout packs receive general fixes rather than scenario-specific tuning. Follow ownership boundaries for future work unless the user authorizes cross-area changes.

All six findings are fixed; there is no pending implementation step from that request. Deployment, hosted/browser/device rehearsal, real ElevenLabs playback and operational latency measurement remain separate work. RDS is provisioned in us-west-2; older deployment templates need region alignment before deployment. Render application deployment remains unverified. The weekday-proxy weekend scenario is a documented proposal; official weekend baselines remain unknown. Mobile broadcasts, schedule screens, preference editing, release and stored read receipts remain outside current delivered scope.

Before further work, inspect the complete working-tree diff and the current documentation. Earlier audit test counts describe earlier checkpoints. Preserve the fixes, approved policies and explicit verification limits above.
