**Purpose:** create deterministic test datasets that exercise every scenario hidden in the brief, without touching the supplied data.
**Owns:** `scripts/synth/generate.py`, `scenarios.py`, `validate.py`, `test_synth.py`; output goes to `data/synthetic/<name>/`, which is gitignored and never committed.
**Standard library only:** `csv`, `json`, `random.Random(seed)`, `datetime`, `zoneinfo`, `argparse`, `hashlib`.

### Rules
- Never modify `data/*.csv`. Use a different date and different ID prefixes (`EVT-T`, `CON-T`, `PHY-T`, `H-T`), as the organizers recommended.
- Use the same 9 files with **identical headers** to the supplied data.
- No `datetime.now()`, no global `random`, rows written in sorted order, `lineterminator='\n'`.
- Expected answers come from what the generator built, never from running the backend engine (that would just check the engine against itself).
- No invented outside factors, and no multi-day history.

### Tasks
1. Write a schema spec (`scripts/synth/schema.py`) listing the headers of all 9 files plus the 20 event types and the exact description strings the backend's sample-CSV adapter (`sample-csv-v1`) recognises → check: a test compares it with the supplied headers.
2. Command line: `generate.py --seed N --date YYYY-MM-DD --now HH:MM --prefix T --scale 1 --out DIR` → check: `--help` works and bad arguments fail with a clear error.
3. Reference files: hospitals in 4 US time zones, on-shift and off-shift physicians, a credential matrix of `Y`/blank, a 24-hour weekday baseline per hospital, and coverage blocks covering 24 hours with no overlaps → check: `validate.py` passes.
4. Event engine: generate each consult's lifecycle following the stage order, with skipped stages allowed (phone-only consults skip video), and calls and video matched to the right physician → check: no consult has an event before its `consult_received`.
5. One function per hidden situation in `scenarios.py`, each recording the IDs involved and the result the detector should produce:
   - stroke consult triaged but unassigned, with repeated routing failures;
   - a hospital surging above its hourly 90th-percentile baseline;
   - two physicians 40 minutes from shift end with unfinished notes;
   - a physician going temporarily unavailable while holding an assigned stroke consult;
   - camera active with no Synapse session;
   - agent offline but looking available;
   - a late `video_started` event;
   - an exact duplicate event;
   - uneven workload caused by credentials;
   - a call ringing while most physicians are busy;
   - exactly one off-shift physician eligible.

   Check: every situation appears in the manifest with its expected result.
6. Expected snapshots: `snapshot_physicians_HHMM.csv` and `snapshot_open_consults_HHMM.csv`, in the same format as the supplied snapshots → check: the backend's replay matches them; any mismatch goes to the backend owner as an issue.
7. `manifest.json` per dataset: seed, date, the "now" time, generator version, the scenario list, and the intentional duplicate and late event IDs → check: it loads with `json`.
8. Datasets to produce:
   - **practice-0407:** a normal Tuesday at 18:20.
   - **dst-1101:** an overnight shift crossing the November 1 daylight-saving change, with "now" at 06:20. It also checks that the missing weekend baseline shows as "unknown".
   - **live-0317:** an append file for March 17 (test cases T23 to T27 from the PRD), event prefix `EVT-L`, rehearsed only in a throwaway database.
   - **splitshift:** the off-shift roster with `next_shift_end`, `offers_sent_last_7d` and `open_offer` added. One physician is eligible, and each of the others fails exactly **one** of R1 to R8, covering all 8 rules.
   - **trap:** a joining physician credentialed at the gap hospital plus 3 others, with enough baseline demand that naive "fewest consults" routing would flood them.

   Check: `validate.py` passes on each.
9. `validate.py`:
   - Headers match exactly; every timestamp has a UTC offset; rows sorted by `ingested_at`.
   - Event IDs unique except the duplicates listed in the manifest; all referenced IDs exist.
   - Stage order never goes backwards; shifts don't overlap.
   - No columns that look like patient data.
   - Check: it also passes on the original `data/` files.
10. Same-output test: generate twice and compare SHA-256 hashes → check: the hashes are identical.
11. `--scale 10` and `--scale 100` multiply consults and events with unique IDs, for the backend's latency measurements → check: row counts scale as expected and the data still validates.
12. Tests run with `python -m unittest discover scripts/synth`. Ask whoever owns CI to add that step, plus a step that generates the datasets before backend tests (the CI runners don't have the gitignored `data/` folder) → check: CI is green.

**Out of scope:** detection logic, changes to the backend, ML-generated data, and committing generated CSVs.
