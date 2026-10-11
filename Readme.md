# Sevaro Command Center

Hospital physician operations: reconstruct consult activity, identify bottlenecks and workload risk, and make credential-aware dispatch decisions explainable.

The app always uses the production database and accounts, locally too; there is no Docker or local database. Copy `.env.example` to `.env`, fill in the production `CC_DATABASE_URL`, `CC_USERS` and `CC_AUTH_SECRET`, then from this directory:

```sh
make backend
make web
```

The API is at `http://localhost:8000` and the web app at `http://localhost:5173`. Sign in with your production account. See the [backend guide](backend/README.md) for setup and tests.

- [PRD v2.2](docs/Sevaro%20Command%20Center%20PRD%20v2.md): scope, corrected fixture expectations, acceptance tests and operations priorities.
- [Backend architecture](docs/Command%20Center%20Backend%20Scaffold.md): target interfaces, state consistency and performance requirements.
- [Fixture review](docs/Backend%20Scaffold%20Review.md): source-data findings and outstanding decisions.
- [Backend foundation](backend/README.md): implemented features, local setup and deferred gates.
- [P2 backend handoff](docs/P2-Backend.md): G1–G8 domain interfaces, verification, and team integration.
- [Deployment](docs/Deployment.md): Render first, AWS fallback, Azure last resort.

The supplied CSVs live in the gitignored `data/` folder and remain unchanged. Run the independent read-only audit with:

```sh
python3 scripts/audit_sample_data.py --data-dir data
```

The scaffold is a foundation for implementation. Core completion requires the PRD's detection, coverage, live-data and consistency tests; passing foundation tests alone is insufficient.
