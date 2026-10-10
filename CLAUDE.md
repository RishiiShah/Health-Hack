# Claude instructions: Sevaro Command Center

@AGENTS.md

## Read first
- Problem: `problem/Sevaro_…_Command_Center.pdf`. Scope and gates: `docs/Sevaro Command Center PRD v2.md`.
- Boundaries, API contract, ElevenLabs, RDS and allowed dependencies: `docs/00-Boundaries-and-Contracts.md`.
- Each person's task doc is in `docs/` (Web-Anish, Web-Joy, Mobile-Hitanshu, Mobile-Chandan, Synthetic-Data-Krish).

## Boundaries
- Edit only the area of the person you're working for (see the ownership table). Needing a change elsewhere means writing an issue, not editing the file.
- The server is the only place rules are computed. Web and mobile only display them.
- Never edit generated files (`web/src/api/types.gen.ts`) or the supplied `data/*.csv`.

## Engineering rules
- Standard library first: Python stdlib, browser APIs (`fetch`, `WebSocket`, `Intl`, `Audio`), the Flutter SDK. Any new dependency needs a reason in the PR and a row in the allowed-dependencies table.
- Use deterministic rules only, and no AI/ML in routing or operations decisions. ElevenLabs only reads out text that has already been decided, and only from the server.
- Time always comes from the injected clock; never call `now()` inside rule logic. Timestamps must carry a UTC offset.
- No hard-coded sample IDs in app code. Sample-data IDs belong only in tests.
- Notifications carry hospital names, hours and start time only: no patient data and no consult details.
- Keep it simple: no speculative abstractions, no configuration nobody asked for, no dead code.

## Commands
- Backend: `cd backend && pytest` (needs Postgres: `docker run -d --name cc-pg -e POSTGRES_PASSWORD=postgres -p 127.0.0.1:5432:5432 postgres:17`)
- Web: `cd web && npm run gen:api && npm test && npm run build`
- Mobile: `cd mobile && flutter test && flutter build web`
- Synthetic data: `python3 scripts/synth/generate.py --seed 1 --date 2026-04-07 --now 18:20 --prefix T --out data/synthetic/practice-0407`, then `python3 -m unittest discover scripts/synth`

## Before pushing
- Run the tests for your area. If you touched `backend/`, run the backend tests too.
- Never commit `data/`, `.venv`, databases, `.env` files or API keys.
- Commit messages: one imperative subject line of about 50 characters.
