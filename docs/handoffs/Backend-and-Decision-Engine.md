# Backend and decision-engine handoff

2026-10-11; fix commit `9fe1333`, branch `rishi`. See the
[E2E audit](../E2E-Audit-2026-10-11.md) for evidence and reproduction commands.

## Current contract

- Python 3.14.7, PostgreSQL, one worker/instance; deterministic replay and explicit constraints.
- Six official Sevaro references are pinned. Event CSVs append; missing official IDs are held. They cannot replace or extend reference data.
- Severity-first lexicographic attention ordering; ordinal display score. Fallbacks are alternatives. Joining physician versus busiest peer bound applies to baseline demand; hospital, waiting and peer-harm constraints apply to all scenarios.
- Offer acceptance reserves the agreed coverage but routing awaits observed arrival. `/me/shift.on_shift` is authoritative for attendance; a scheduled end is not proof of presence.
- Hourly inventory/expected demand are implemented. Official weekend baseline remains unknown. The displayed horizon reaches exact shift boundaries; routing retains its documented 90-minute simulation.

## Delivered in this cohort

`scripts/hosting_smoke.py` uses replay time and a known hospital. New API tests
cover paused-clock seeding and idempotency. `scripts/e2e_server.py` supplies a
safe localhost fixture and restart state; safety tests reject remote/unrelated
databases. The full backend suite passed **383 tests**.

## Next actionable work

1. Implement the separately selected read-only [weekend planning scenario](../Judging-and-Weekend-Assumptions.md), starting with its eight acceptance cases. Never fabricate official weekend p90 or reuse Tuesday shifts as confirmed weekend capacity.
2. Keep scenario outputs out of events, offers, live routing and approvals. Expose assumption version, source fingerprint, inputs, unknowns and deterministic replay identity.
3. Measure latency on the hosted database before claiming speed or scalability. Multiple application replicas need explicit recovery/concurrency design; existing transaction tests alone do not establish that support.

Run native tests with `backend/.venv/bin/python -m pytest -q backend/tests` and
a **local disposable PostgreSQL admin** in `CC_TEST_DATABASE_URL`. Docker
`make backend-test` omits private source packs; report those skips explicitly.
Do not commit source CSVs, test state, auth files, database dumps or credentials.
