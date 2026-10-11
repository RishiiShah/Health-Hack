# Deterministic practice datasets

Run from the repository root with Python 3.14.7. The generator and validator use
only the standard library, import no backend code, read no supplied CSVs and make
no network requests. Outputs are ignored under `data/synthetic/`.

```sh
python -m unittest discover scripts/synth -v
python scripts/synth/generate.py --suite --out data/synthetic
python scripts/synth/validate.py data/synthetic/practice-0407
```

To generate another independent day:

```sh
python scripts/synth/generate.py --seed 7 --date 2026-04-07 --now 18:20 --prefix T --scale 10 --out data/synthetic/scale-10
```

The same arguments produce identical bytes and SHA-256 manifests. A seeded
local RNG varies completed background-session timing. Invalid arguments,
ambiguous/nonexistent Eastern clock times, and output directories containing
unowned files are rejected. Supplied `data/*.csv` cannot be overwritten.

| Dataset | Purpose |
| --- | --- |
| `practice-0407` | Tuesday 18:20, all eleven operational scenarios |
| `dst-1101` | October 31 overnight shift, November 1 06:20 snapshot; repeated 01:20 offsets represent sixty elapsed minutes; weekend baseline unknown |
| `live-0317` | Independent March 17 base and future append rehearsing T23–T27 semantics |
| `splitshift` | One eligible physician and eight others each failing one R1–R8 rule |
| `trap` | Joiner credentialed at the gap and three other hospitals; naive routing spills outside the offer |

Each dataset has nine core CSVs and `manifest.json`. Snapshot filenames use the
requested `HHMM`. Hospital IDs in credential columns follow the generated
namespace while preserving the supplied header structure. `splitshift` adds
`next_shift_end`, `offers_sent_last_7d` and `open_offer`; actual backend offer
history is supplied separately in `support/offer_history.csv`. The sample loader
does not turn those extra roster history columns into persisted offers.

Expected snapshots come from authored lifecycle outcomes and counts in
`scenarios.py`, independently of application replay. The backend's public
`test_synth_replay.py` compares every snapshot column, validates all eligibility
rejections and checks key detector findings and trap restrictions. It also
replays the live append after advancing the injected clock, without reset.
The generator unittest checks hashes, all five datasets, bad inputs, corruption,
source protection and 10×/100× scaling. Source-header comparison runs only when
the private kit exists and is explicitly skipped otherwise.

The validator is read-only and also accepts the original sample directory:

```sh
python scripts/synth/validate.py data
```

It checks headers, offsets, ingestion ordering, allowed exact duplicates,
reference IDs, receipt causality, monotonic lifecycle stages, matched call/video
sessions, credentials, shift endpoints, complete nonoverlapping coverage,
weekday baseline and generated hashes. Time-only sample columns deliberately
retain their original format; offset requirements apply to full timestamps.

Scale 10/100 multiplies consult lifecycles and their events, not the 36 initial
roster signals or hospital/physician references. These cases measure replay
volume; they do not assert that a physician can perform simultaneous sessions
at that scaled volume. No hosting performance or latency improvement is claimed.

Use these datasets only in disposable rehearsal databases. The live fixture
uses independent IDs and references; kit-specific expected counts remain covered
by protected-kit tests. Never load synthetic references into the production
database holding the official reference kit, or commit generated CSVs.
