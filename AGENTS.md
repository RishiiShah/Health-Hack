# Engineering preferences

- Prefer Python standard-library tools for storage, CSV/JSON parsing, clocks, HTTP utilities and configuration.
- When the standard library is insufficient, use a small, direct implementation before adding a dependency. Avoid custom protocol implementations when an established framework is needed for correctness.
- Add third-party packages only for an implemented requirement and document why they are needed. Avoid unused extras, speculative abstractions, dead code and repeated work.
- Keep accuracy and deterministic replay ahead of shortcuts. Measure operational latency before claiming performance improvements.
- Use Python 3.14.7 and keep CI, the Docker image and runtime documentation aligned. Hosting preference: Render, AWS, then Azure.
- Never commit source data, local environments, databases or secrets. Run the backend tests before pushing implementation changes.
