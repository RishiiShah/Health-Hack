# Persistent reference data on localhost and Render

The database stores the six reference CSVs, their service date, and the normalized
physician/hospital references in one activation transaction. Uploaded references
take precedence over `CC_DATA_DIR` and recover on restart. Events, offers and the
clock are retained by the upload.

The existing local demo at `http://127.0.0.1:8010` now contains **Sevaro official
reference kit**, service date **2026-03-17**, **12 hospitals** and **14 physicians**.
It retained its **1,166 stored events**, reference revision **1** and paused
18:20 ET clock. The upload advanced the publication revision to **5**. No source
CSV or answer key was changed.

An actual local backend restart was verified: the fingerprint, counts, stored
events, publication revision and fixed clock recovered unchanged. The isolated
browser workflow check used a separate disposable database.

Its reference SHA-256 is:

```text
81602969911fe81fc1d5db5a51595fb5124d07ac5f5e97623a21e1232701d72d
```

## Production RDS load

The configured production AWS RDS database, **commandcenter** in **us-west-2**,
now stores the same six CSVs and normalized references: **Sevaro official
reference kit**, service date **2026-03-17**, **12 hospitals**, **14 physicians**,
and the SHA-256 above. Its existing normalized references already matched; the
load added the missing CSV source needed to reconstruct operational tables at
backend startup. No application connections were active during the load.

The transaction advanced publication revision **2 → 3** and retained reference
revision **1** and dataset generation **1**. Hash comparisons confirmed that all
**1,163 existing events**, held-event and quarantine tables, ingest statistics,
and other metadata remained unchanged. No clock override or offer tables existed;
none were created. The connection used certificate and hostname verification
(`sslmode=verify-full`) with **TLS 1.3** and the official RDS CA bundle.

An independent reconnect verified persistence, rebuilt both normalized and
operational references from the saved CSVs, and checked their equality with the
validated source. The recovered operational data contains **1,440 baseline
entries**, coverage requirements for **12 hospitals**, and **6 off-shift roster
entries**. This loaded the database directly; a Render service was not deployed
or tested in this step. A backend configured to use this database loads these
persisted references at startup.

## Load and verify

From the repository root, for the existing local demo:

```sh
python3 scripts/upload_references.py data --url http://127.0.0.1:8010 --service-date 2026-03-17 --name "Sevaro official reference kit"
python3 scripts/upload_references.py data --url http://127.0.0.1:8010 --service-date 2026-03-17 --check
```

For the normal `make backend` stack, substitute port **8000**. For Render, after
deploying the backend and configuring its persistent PostgreSQL database and
accounts, use the same files and date:

```sh
python3 scripts/upload_references.py data --url https://YOUR-SERVICE --service-date 2026-03-17 --name "Sevaro official reference kit"
python3 scripts/upload_references.py data --url https://YOUR-SERVICE --service-date 2026-03-17 --check
```

The script signs in interactively, or uses `CC_API_TOKEN` when already configured
in the shell. The account needs `admin.inject`. Source CSVs remain local; the
authenticated HTTPS upload stores them in the hosted database. They are not
included in the Docker image or committed to Git.

A matching upload is a read-only verification. `--check` never writes. Runtime
pins the official Sevaro fingerprint, rejects replacement with HTTP 409, and
checks the fingerprint again at startup. There is no replacement flag. A first
bootstrap is followed by a readback comparison. The production RDS load above
prepares future Render hosting; no Render service has been deployed. Synthetic
test fixtures explicitly override the fingerprint only in disposable test
processes; their initialized kit is also immutable through the API.

## Compare environments

`GET /admin/references` returns `persisted`, counts, reference/publication
revisions, and a manifest with the dataset SHA-256, service date, and six file
hashes. It does not return the CSV contents. The fingerprint hashes a canonical
JSON encoding of the decoded CSV text and service date; dataset labels and
dictionary order do not affect it. Formatting changes do affect it.

Run `--check` against each endpoint to establish identical persisted references.
For matching decisions, also use the same event stream, offer history, simulation
clock and backend version. A new hosted database has no events: load the supplied
base stream through the existing Data page or `/events/csv`, then set the desired
simulation time with `/admin/clock`. For the official base rehearsal this is
`2026-03-17T18:20:00-04:00` with `paused: true`. Reference equality alone does not
make two different replay histories identical.

Restart recovery, retained events, authentication, manifest changes, matching
upload skips and mismatched-version checks are covered by synthetic tests in
`backend/tests/test_reference_database.py` and `test_upload_references.py`.


### Hourly baseline and surge forecast

The official `baseline_hourly_volume.csv` has 288 source rows (12 hospitals × 24 ET hours), with 12 weeks sampled, and expands to 1,440 weekday/day-hour lookup entries. It supplies **no weekend baseline**. `coverage_requirements.csv` supplies staffing blocks; the roster supplies capacity and shift changes. These files are already persisted with the fixed reference kit in the production database; event uploads cannot append to or replace them.

Data → Reference data shows the loaded baseline row count, sampling weeks, staffing block count, roster count and per-hospital weekday coverage. The command center shows observed trailing-60-minute demand against that hour’s p90, its historical mean, and expected arrivals over the same horizon as coverage. Expected arrivals integrate hourly means with partial hours and DST in elapsed UTC time; a missing hour leaves the whole total unknown. Baseline values are finite/nonnegative, weekday/hour keys valid, and ET baseline starts must be whole unzoned hours. Sampling weeks, when supplied, must be positive integers.

A surge remains the problem’s deterministic rule: distinct live consults in the trailing 60 minutes strictly exceed that hour’s p90, adding one required physician. Forecast coverage accounts for scheduled shifts and aging observed receipts. Historical means support expected-demand and intervention stress scenarios; they cannot establish a calibrated probability that a future surge will occur. Additional official weekend/hourly history would be needed for those missing periods; generated scenario packs are not substitutes for the Sevaro references.
