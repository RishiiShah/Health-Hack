# Deployment and judge-demo handoff

2026-10-11; fix commit `9fe1333`, branch `rishi`. This cohort is committed locally;
Render deployment and hosted verification are pending. Production data was not changed.

## Deployment sequence

1. Reconcile Render region/network settings with RDS in **us-west-2**; existing Virginia/us-east-1 templates are not aligned. Follow [Deployment](../Deployment.md) and keep Python 3.14.7 / one worker / one instance.
2. Configure production database/auth/CORS/speech secrets through protected hosting settings. The image contains no source CSVs. Production already has the official references; use the read-only `upload_references.py --check` flow from [Reference Data](../Reference-Data.md).
3. Verify `/ready`, authenticated login/role permissions, exact reference fingerprint, baseline inventory, clock, web API transport and restart persistence on the actual host. Save revision, deployed commit and nonsecret evidence.
4. Rehearse writes in a **separate staging database**: append compatible CSV, verify receipt/history and queue, complete offer loop and observed arrival, then restart. `hosting_smoke.py seed` writes a synthetic consult and belongs only in that disposable database; `verify` checks the previously seeded consult.
5. Verify actual speech-provider playback and a real mobile device. Record failures and timing; do not infer hosted performance from localhost test/build times.

## Judge story

Show the official 18:20 day, source fingerprint, hourly expected demand and an
upcoming shift cliff. Upload a compatible unseen CSV on **Data**: report accepted
and duplicate rows, clock advance, new Critical item, distinct trailing demand,
unchanged references and retained histories. Then Find cover → propose → lead
approve/send → physician accept → “Awaiting arrival” → observed arrival → routing,
schedule and audit update. Acceptance alone must not put the doctor online.

The localhost E2E passed this story and actual stop/start recovery:
**383 backend, 58 web, 149 mobile tests**, builds and browser checks. See the
[audit](../E2E-Audit-2026-10-11.md) and [Judge Test Plan](../Judge-Test-Plan.md).
Those results do not establish hosted operation, clinical outcomes or compliance.

The development pack's different IDs are correctly held against the official
kit. Use an independent synthetic fixture to rehearse that pack; never swap
production references to make it fit. Official weekend data remains missing;
the [weekday-proxy weekend scenario](../Judging-and-Weekend-Assumptions.md) is a
future read-only planning feature, not a measured predictor to show as delivered.
