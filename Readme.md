# Sevaro Command Center

Hospital physician operations: reconstruct consult activity, identify bottlenecks and workload risk, and make credential-aware dispatch decisions explainable.

Start the authenticated backend and local PostgreSQL from this directory (Docker Desktop running):

```sh
make backend
```

The first run asks you to create a local account. Later runs reuse it. The API is at `http://localhost:8000`; source edits reload automatically. `make backend-down` stops the services without deleting the database. See the [backend guide](backend/README.md) for adding accounts and tests.

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
