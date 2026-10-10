## Goal
Detect, then Decide, then Approve (a person), then Act, then Update, then back to Detect. Don't rebuild Sevaro's existing live-workload view. Every screen should answer "what's wrong, why, and what do we do".

## Who owns what
| Area | Owner | Can edit | Must not edit |
|---|---|---|---|
| `backend/` | Backend (Rishi and backend team) | Engine, API, database, ElevenLabs calls | — |
| `web/src/` Detect screens | Anish | `web/src/detect/*`, `web/src/api/*`, `web/src/App.tsx` | Joy's folders, backend |
| `web/src/` Decide/Act screens | Joy | `web/src/act/*`, `web/src/forecast/*` | `web/src/api/*` (ask Anish), backend |
| `mobile/` screens and flow | Hitanshu | `mobile/lib/screens/*`, `mobile/test/screens/*` | `mobile/lib/data/*` |
| `mobile/` data, audio, deploy | Chandan | `mobile/lib/data/*`, `mobile/lib/audio.dart`, build config | Screens |
| Synthetic data | Krish | `scripts/synth/*`, the generated output folder `data/synthetic/` (not committed) | `data/*.csv` originals, `backend/` |
| Docs | Each person owns their own doc | Your own doc | Other people's docs |

**Rules for crossing a boundary**
- The client apps never recompute business rules. Levels, scores, eligibility and gaps all come from the server, and the clients only display them.
- Need an API change? Open an issue for the backend owner. They update the backend schema, then Anish regenerates the web types. Nobody edits generated types by hand.
- App code never hard-codes IDs from the sample data (for example `CON-2105`). Those IDs belong only in tests.

## System diagram
```
event CSV / JSON ──► backend (1 process, in-memory replay) ──► RDS PostgreSQL (events, references, offers, audit, audio cache)
                        │  ▲                      │
          WebSocket /ws │  │ REST                 └─► ElevenLabs text-to-speech (server-side only, cached)
                        ▼  │
               web (coordinator + clinical lead)        mobile (off-shift physician: accept/decline only)
```

## API contract v1 (backend owns this; freeze it at the start of the hackathon)
| Method and path | Role | Used by |
|---|---|---|
| `GET /health`, `GET /ready` | none | deploy |
| `GET /snapshot` | coordinator, lead | web |
| `WS /ws` | coordinator, lead | web. Sends `{epoch, seq, snapshot}` with the **whole snapshot** on every update; no partial updates |
| `GET /gaps/{gap_id}/candidates` | coordinator, lead | Joy |
| `GET /gaps/{gap_id}/trap-check` | coordinator, lead | Joy |
| `POST /interventions` `{kind: reassign\|escalate, item_id, physician_id?}` | coordinator | Anish |
| `POST /interventions/{id}/authorize` | lead | Joy |
| `POST /offers` `{gap_id, physician_id, start, end}` | coordinator | Joy |
| `POST /offers/{id}/approve` and `/reject {reason}` | lead | Joy. Approving runs the pre-send check and the simulated send in one call |
| `GET /offers`, `GET /audit?gap_id=` | coordinator, lead | Joy |
| `GET /alerts/{item_id}/audio` | coordinator, lead | Anish |
| `GET /m/offer?token=` | physician token | Chandan |
| `POST /m/offer/accept`, `POST /m/offer/decline` `{token}` | physician token | Chandan |
| `GET /m/offer/audio?token=` | physician token | Chandan |
| `POST /events` (JSON batch), `POST /events/csv` | admin | Joy |
| `POST /admin/reset`, `POST /admin/clock` | admin | Joy |

## Roles and authentication (kept simple, standard library only)
- The coordinator, lead and admin each get a fixed demo token from an environment variable. The server checks it with `hmac.compare_digest`. The lead's display name also comes from an environment variable and is written to the audit log as the approver.
- Each physician offer gets a token: an HMAC over `offer_id`, `physician_id` and the expiry time, built with `hmac` and `hashlib`. It works for that one offer only.
- The server enforces every role check. The web UI's role switch is cosmetic.

## Offer states (from the PRD)
Proposed → Approved | Rejected; Approved → Sent; Sent → Accepted | Already filled | Declined | Expired | Withdrawn | Cancelled.
- Two physicians accept for the same gap: the server locks the gap row (`SELECT … FOR UPDATE`), the first commit wins, and the second gets "Already filled".
- When an offer is declined or expires, the server proposes the next-ranked candidate. That new offer still needs the lead's approval.

## ElevenLabs integration (backend implements it; web and mobile only play the audio)
- **Uses:** (1) reading an offer aloud to the physician; (2) speaking a new Critical alert to the coordinator, which the brief allows as an automated low-risk internal alert; (3) announcing "approval requested" to the clinical lead.
- **Call:** `POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}` with an `xi-api-key` header and a JSON body `{text, model_id}`, which returns `audio/mpeg`. It uses `urllib.request` with a 10-second timeout and makes one attempt, with no retry loop.
- **Config:** environment variables `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID` and `ELEVENLABS_MODEL_ID`. The key never reaches a client.
- **Templates:** typed functions that accept only hospital names, times, durations, counts and a reason code. They can't accept consult or patient data, so none can leak into a message. Physician names aren't spoken.
  - Example offer text: "Sevaro split-shift offer. Suncrest Medical Pavilion. 7:15 PM to 9:15 PM Eastern. Requested because of a coverage gap at a hospital you are credentialed for. Expires at 6:52 PM."
- **Cache:** RDS table `tts_audio(sha256 PK, voice_id, model_id, audio BYTEA, created_at)`, keyed on the text plus voice plus model. Offer audio is generated when the offer is sent; alert audio is generated the first time someone requests it.
- **If ElevenLabs fails:** the endpoint returns 503, the clients hide the play button, and the text is still shown. The loop never waits on audio.

## Decision record: Amazon RDS for PostgreSQL
- **Context:** the user requested RDS. The current SQLite-on-disk design ties storage to a single host's disk.
- **Decision:**
  - One RDS PostgreSQL instance, single availability zone for the demo, in us-east-1.
  - Driver: `psycopg[binary]` only. No ORM and no migration tool: a `schema.sql` file using `CREATE TABLE IF NOT EXISTS` runs at startup.
  - One connection per process, with short transactions.
  - Encrypted connections (`sslmode=verify-full` with the RDS certificate bundle).
  - The `CC_DATABASE_URL` environment variable replaces `CC_DB_PATH`.
- **Consequences:**
  - The backend is still **one process**: replay state lives in memory, and RDS only makes data durable.
  - Every commit is a network round trip, so measure p95 ingest time after switching.
  - CI uses a `postgres` service container, and local development uses a Postgres service in Compose.
  - Deployment.md, render.yaml, Compose and CI change in the same PR.
  - The backend can run on Render's Virginia region or on EC2 in us-east-1. Limit the RDS security group to the backend's outbound addresses.
- **Alternatives considered:**
  - Keep SQLite: zero dependencies and already working.
  - Aurora Serverless: more cost and more moving parts.
  - DynamoDB: a poor fit for transactions and audit queries.

## Allowed dependencies (anything else needs a written reason in the PR)
| Area | Allowed | Explicitly not allowed |
|---|---|---|
| Backend | fastapi, uvicorn, pydantic (existing); psycopg[binary] (needed for RDS); pytest, httpx (tests) | requests, the ElevenLabs SDK, ORMs, alembic, celery, redis |
| Web | react, react-dom, vite, typescript; openapi-typescript (development only) | Tailwind, ECharts, router, state, UI-kit, date or HTTP libraries |
| Mobile | Flutter SDK, `http`, `web` (both made by the Dart team) | state-management, router, Firebase or audio plugins |
| Synthetic data | Python standard library only | numpy, pandas, faker |
| Web tests | Node's built-in `node --test` (Node 24) | jest, vitest |

## Shared definition of done
- Your own tests pass. The backend tests pass before every push.
- The work is demonstrated against the 18:20 sample data.
- The live test works: new events show up without a restart.
- No patient data appears in any notification.
