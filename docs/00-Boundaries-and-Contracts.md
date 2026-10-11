## Current contract

See [document authority](README.md) for current implementation, historical
handoffs and open policy differences. This file describes implemented contracts;
the PRD's weighted G15 score is not the backend's current ordering policy.

## Goal
Detect, then Decide, then Approve (a person), then Act, then Update, then back to Detect. Don't rebuild Sevaro's existing live-workload view. Every screen should answer "what's wrong, why, and what do we do".

## Who owns what
| Area | Owner | Can edit | Must not edit |
|---|---|---|---|
| `backend/` | Backend (Rishi and backend team) | Engine, API, database, ElevenLabs calls | — |
| `web/src/` shell, role routing, Detect and physician screens | Anish | `web/src/App.tsx`, `web/src/auth/*`, `web/src/api/*`, `web/src/detect/*`, `web/src/physician/*` | Joy's folders, backend |
| `web/src/` Decide/Act and clinical-lead screens | Joy | `web/src/act/*`, `web/src/forecast/*`, `web/src/lead/*` | `web/src/api/*` (ask Anish), backend |
| `mobile/` screens, role routing and flow | Hitanshu | `mobile/lib/screens/*`, `mobile/lib/main.dart`, `mobile/test/screens/*` | `mobile/lib/data/*` |
| `mobile/` data, auth, audio, deploy | Chandan | `mobile/lib/data/*`, `mobile/lib/audio.dart`, build config | Screens |
| Synthetic data | Krish | `scripts/synth/*`, the generated output folder `data/synthetic/` (not committed) | `data/*.csv` originals, `backend/` |
| Docs | Each person owns their own doc | Your own doc | Other people's docs |

**Rules for crossing a boundary**
- The client apps never recompute business rules. Levels, scores, eligibility and gaps all come from the server, and the clients only display them.
- The client apps never decide who may do what. They choose which dashboard to load from `GET /me`; the server enforces every permission on every request.
- Need an API change? Open an issue for the backend owner. They update the backend schema, then Anish regenerates the web types. Nobody edits generated types by hand.
- App code never hard-codes IDs from the sample data (for example `CON-2105`). Those IDs belong only in tests.

## System diagram
```
event CSV / JSON ──► backend (1 process, in-memory replay) ──► RDS PostgreSQL (events, references, offers, audit, audio cache)
                        │  ▲                      │
          WebSocket /ws │  │ REST                 └─► ElevenLabs text-to-speech (server-side only, cached)
                        ▼  │
     web: coordinator, clinical lead, physician      mobile: clinical lead, physician (coordinator → "use web")
     (dashboard chosen by GET /me role)              (dashboard chosen by GET /me role)
```

## API contract v1 (backend owns this; freeze it at the start of the hackathon)
| Method and path | Role | Used by |
|---|---|---|
| `GET /health`, `GET /ready` | none | deploy |
| `GET /me` → `{role, display_name, physician_id, permissions[]}` | any valid token | Anish, Chandan. Both apps pick the dashboard from this |
| `GET /snapshot` | coordinator, lead | web; mobile lead (polled; the response is cached server side) |
| `WS /ws` | coordinator, lead | Available API transport. Sends `{epoch, seq, snapshot}` with the **whole snapshot**; current web uses serialized REST polling |
| `GET /gaps/{gap_id}/candidates` | coordinator, lead | Joy, Hitanshu |
| `GET /gaps/{gap_id}/trap-check` | coordinator, lead | Joy, Hitanshu |
| `POST /interventions` `{kind: reassign\|escalate, item_id, physician_id?}` | coordinator | Anish |
| `POST /interventions/{id}/authorize` | lead | Joy, Hitanshu |
| `POST /offers` `{gap_id, physician_id, start, end}` | coordinator | Joy |
| `POST /offers/{id}/approve` and `/reject {reason}` | lead | Joy, Hitanshu. Approving runs the pre-send check and the simulated send in one call |
| `GET /offers`, `GET /offers/{id}` | coordinator, lead: all offers; physician: **only their own** (the server filters) | everyone |
| `POST /offers/{id}/accept`, `POST /offers/{id}/decline` | physician, own offer only | Anish, Hitanshu |
| `GET /offers/{id}/audio` | lead; physician, own offer only | everyone |
| `GET /audit?gap_id=` | coordinator, lead | Joy, Hitanshu |
| `GET /schedule` | coordinator, lead | Web schedule: roster, accepted intervals and pending offers; incomplete future ends remain unknown |
| `GET /alerts/{item_id}/audio` | coordinator, lead | Anish, Hitanshu |
| `POST /events` (JSON batch), `POST /events/csv` | `admin.inject`: coordinator, lead, admin | Joy |
| `POST /admin/reset`, `POST /admin/clock` | `admin.inject`: coordinator, lead, admin | Joy |
| `POST /admin/references` `{files: {name: csv text}, service_date?, name?}` (the six reference CSVs) | `admin.inject`: coordinator, lead, admin | script / Joy's Data page |
| `GET /admin/references` | `admin.inject` | Persisted reference counts, service date and SHA-256 manifest; no CSV contents |
| `GET /admin/uploads` | `admin.inject` | Latest 20 durable CSV receipts across stream generations: original-byte hash, actor, filename, reference fingerprint and per-row results at upload time |
| `POST /admin/physician-tokens` `{physician_id}` | admin | demo setup: issues a physician's sign-in link |

## Roles, authentication and RBAC (kept simple, standard library only)
**Who uses which app.** The clinical lead and the physician each get a dashboard on **both** web and mobile, so either can work on the go. The coordinator works at a desk and uses web only; the mobile app shows a coordinator "Use the web dashboard".

| Role | Web dashboard | Mobile dashboard |
|---|---|---|
| Coordinator | Full command center: Detect, forecast, candidates, propose offers, interventions | "Use the web dashboard" screen |
| Clinical lead | Approval queue (home), stroke-risk Critical items, offer tracker, audit | Same content in compact form: approvals (home), stroke-risk items, offer status |
| Physician | My offers (accept/decline, countdown, audio) and my accepted shifts | Same |
| Admin | API/setup tooling; no password-account dashboard | none |

**Tokens.**
- Normal web/mobile sign-in uses `POST /auth/login` with email and password, then `GET /auth/me`; the returned account role chooses the dashboard. Web stores the session in the browser tab; native mobile holds it in memory. A 401 clears the session. `CC_AUTH_CONFIG` supplies accounts/signing secret when set and takes precedence over `CC_USERS`/`CC_AUTH_SECRET`. The optional token mechanisms below coexist with accounts on the API; they are not the current web password-sign-in flow.
- Coordinator, lead and admin each get a fixed demo token from an environment variable, checked with `hmac.compare_digest`. The lead's display name also comes from an environment variable and is written to the audit log as the approver.
- A physician token is an HMAC over `physician_id` and an expiry time (`hmac`, `hashlib`), issued by `POST /admin/physician-tokens`. It identifies one physician, not one offer, so the same sign-in works for every offer they get. The simulated offer message links to `<app>/?token=…&offer=<id>`.
- Token-based physician links remain an API/demo mechanism; the current password-sign-in web UI does not implement a token-paste login screen.

**Permissions** (returned by `GET /me`; the server checks the same table on every request):

| Permission | Coordinator | Lead | Physician | Admin |
|---|---|---|---|---|
| `ops.view` (snapshot, WebSocket, candidates, trap check, audit) | ✓ | ✓ | | |
| `ops.intervene` (reassign, escalate, propose offers) | ✓ | | | |
| `approvals.decide` (approve/reject offers, authorize interventions) | | ✓ | | |
| `offers.view_all` | ✓ | ✓ | | |
| `offers.view_own`, `offers.respond` | | | ✓ | |
| `admin.inject` (events, reset, clock, physician tokens) | ✓ | ✓ | | ✓ |

- The client shows a button only when `/me` lists its permission, but hiding a button is a convenience, not security. A request without the permission gets 403; an offer belonging to another physician gets 404, so offer IDs can't be probed.
- A 401 (missing, wrong or expired token) sends either app back to the sign-in screen.

## Offer states (from the PRD)
Proposed → Approved | Rejected; Approved → Sent; Sent → Accepted | Already filled | Declined | Expired | Withdrawn | Cancelled.
- Two physicians accept for the same gap: the server locks the gap row (`SELECT … FOR UPDATE`), the first commit wins, and the second gets "Already filled".
- When an offer is declined or expires, the server proposes the next-ranked candidate. That new offer still needs the lead's approval.

## ElevenLabs integration (backend implements it; web and mobile only play the audio)
- **Uses:** (1) reading an offer aloud to the physician; (2) speaking a new Critical alert to the coordinator, which the brief allows as an automated low-risk internal alert; (3) announcing "approval requested" to the clinical lead, on web or phone.
- **Call:** `POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}` with an `xi-api-key` header and a JSON body `{text, model_id}`, which returns `audio/mpeg`. It uses `urllib.request` with a 10-second timeout and makes one attempt, with no retry loop.
- **Config:** environment variables `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID` and `ELEVENLABS_MODEL_ID`. The key never reaches a client.
- **Templates:** typed functions that accept only hospital names, times, durations, counts and a reason code. They can't accept consult or patient data, so none can leak into a message. Physician names aren't spoken.
  - Example offer text: "Sevaro split-shift offer. Suncrest Medical Pavilion. 7:15 PM to 9:15 PM Eastern. Requested because of a coverage gap at a hospital you are credentialed for. Expires at 6:52 PM."
- **Cache:** RDS table `tts_audio(sha256 PK, voice_id, model_id, audio BYTEA, created_at)`, keyed on the text plus voice plus model. Offer audio is generated when the offer is sent; alert audio is generated the first time someone requests it.
- **If ElevenLabs fails:** the endpoint returns 503, the clients hide the play button, and the text is still shown. The loop never waits on audio.

## Decision record: Amazon RDS for PostgreSQL
- **Status:** implemented; production RDS **commandcenter** is provisioned in **us-west-2** and reference loading/reconnect verification succeeded. Application hosting remains unverified; see [Deployment](Deployment.md).
- **Context:** the app will be stress tested, and the earlier SQLite-on-disk design tied storage to a single host's disk.
- **Decision:**
  - One RDS PostgreSQL database; the original region plan was us-east-1, while the configured instance is us-west-2. Its high-availability configuration was not inspected.
  - Driver: `psycopg[binary]` only. No ORM and no migration tool: schema statements in the owning modules use `CREATE TABLE IF NOT EXISTS` at startup.
  - Separate event, offer, intervention and speech-cache connections in one process, with short transactions.
  - Encrypted connections (`sslmode=verify-full` with the RDS certificate bundle).
  - The `CC_DATABASE_URL` environment variable replaces `CC_DB_PATH`.
- **Consequences:**
  - The backend is still **one process**: replay state lives in memory, and RDS only makes data durable.
  - Each commit is a few network round trips (inserts are batched), so measure p95 ingest time against RDS.
  - Each commit checks the revision this process loaded; if another instance wrote first (deploy overlap), it reloads from RDS and retries once.
  - Caching is in process: `/snapshot` reuses its encoded response until a commit, a newly visible event or the next clock second. Redis/ElastiCache was rejected: with one process it only adds a network hop.
  - CI uses a `postgres` service container, and local development uses a Postgres service in Compose.
  - Deployment.md, render.yaml, Compose and CI change in the same PR.
  - Align the application region with the configured RDS instance before hosting. Limit the RDS security group to the backend's outbound addresses.
- **Alternatives considered:**
  - Keep SQLite: zero dependencies and already working.
  - Aurora Serverless: more cost and more moving parts.
  - DynamoDB: a poor fit for transactions and audit queries.

## Allowed dependencies (anything else needs a written reason in the PR)
| Area | Allowed | Explicitly not allowed |
|---|---|---|
| Backend | fastapi, uvicorn, pydantic (existing); psycopg[binary] (needed for RDS); pytest, httpx (tests) | requests, the ElevenLabs SDK, ORMs, alembic, celery, redis |
| Web | react, react-dom, vite, typescript; openapi-typescript (development only); existing tailwindcss and @tailwindcss/vite for the implemented landing-page styles | ECharts, router, state, UI-kit, date or HTTP libraries |
| Mobile | Flutter SDK, `http`, `web` (both made by the Dart team) | state-management, router, Firebase or audio plugins |
| Synthetic data | Python standard library only | numpy, pandas, faker |
| Web tests | Node's built-in `node --test` (Node 24) | jest, vitest |

## Shared definition of done
- Your own tests pass. The backend tests pass before every push.
- The work is demonstrated against the 18:20 sample data.
- The live test works: new events show up without a restart.
- No patient data appears in any notification.
