"""Single-writer PostgreSQL transactions for accepted, held and rejected events."""
import json
from pathlib import Path
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from app.models import Event

IMAGE_CA = "/etc/ssl/certs/rds-global-bundle.pem"  # baked into the Docker image


def usable_ca(url: str) -> str:
    """A database URL copied from a laptop names a CA file that does not exist on the host; use the image's bundle."""
    root = conninfo_to_dict(url).get("sslrootcert")
    if root and root != "system" and not Path(root).is_file() and Path(IMAGE_CA).is_file():
        return make_conninfo(url, sslrootcert=IMAGE_CA)
    return url


POOL_SIZE = 4  # per store; an offer command holds one connection while it reads the context through another


def pool(url: str, row_factory=dict_row) -> ConnectionPool:
    """Every server connection comes from a small pool, so one slow query no longer queues every request behind it.
    Waits are bounded: a lock wait fails after 15 s, the server ends a session left idle in a transaction for 60 s
    (so a stuck instance cannot hold the offer lock for every other one), and a dead or unreachable database fails
    within seconds instead of hanging a thread that holds a lock. A connection is checked before it is handed out,
    so one the database dropped is replaced instead of failing the request."""
    connections = ConnectionPool(url, min_size=1, max_size=POOL_SIZE, timeout=15, open=False, check=ConnectionPool.check_connection,
                                 kwargs=dict(autocommit=True, row_factory=row_factory, connect_timeout=10,
                                             keepalives=1, keepalives_idle=30, keepalives_interval=10, keepalives_count=3,
                                             options="-c timezone=UTC -c lock_timeout=15s -c idle_in_transaction_session_timeout=60s"))
    try:
        connections.open(wait=True, timeout=15)
    except Exception:
        connections.close()  # or its workers keep retrying a database this process gave up on
        raise
    return connections


# Serializes schema creation when an old and a new instance start together.
SCHEMA_LOCK = 7_310_001
SCHEMA = """
CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS events (dataset_generation INTEGER NOT NULL, event_id TEXT NOT NULL, event_time TIMESTAMPTZ NOT NULL, ingested_at TIMESTAMPTZ NOT NULL, received_at TIMESTAMPTZ NOT NULL, event_type TEXT NOT NULL, consult_id TEXT, physician_id TEXT, hospital_id TEXT, consult_type TEXT, value TEXT, source TEXT NOT NULL, time_offset TEXT, raw_json TEXT NOT NULL, adapter_version TEXT NOT NULL, PRIMARY KEY(dataset_generation,event_id));
CREATE INDEX IF NOT EXISTS events_by_time ON events(dataset_generation,event_time,ingested_at,event_id);
CREATE TABLE IF NOT EXISTS quarantine (id BIGSERIAL PRIMARY KEY, dataset_generation INTEGER NOT NULL, received_at TIMESTAMPTZ, reason TEXT NOT NULL, raw_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS held_events (dataset_generation INTEGER NOT NULL, event_id TEXT NOT NULL, event_json TEXT NOT NULL, expires_at TIMESTAMPTZ NOT NULL, expired BOOLEAN NOT NULL, PRIMARY KEY(dataset_generation,event_id));
CREATE TABLE IF NOT EXISTS event_uploads (batch_id TEXT PRIMARY KEY, dataset_generation INTEGER NOT NULL, received_at TIMESTAMPTZ NOT NULL, payload_json TEXT NOT NULL);
INSERT INTO metadata VALUES('revision','0'),('dataset_generation','1') ON CONFLICT DO NOTHING;
"""
EVENT_COLUMNS = tuple(Event.model_fields)


class StaleRevision(RuntimeError):
    """Another writer committed since this process last loaded the event log."""


class EventDatabase:
    def __init__(self, url: str):
        self.url = url
        self.pool = pool(url)
        try:
            with self.pool.connection() as conn, conn.transaction():
                conn.execute("SELECT pg_advisory_xact_lock(%s)", (SCHEMA_LOCK,))
                for statement in filter(str.strip, SCHEMA.split(";")):
                    conn.execute(statement)
        except Exception:
            self.pool.close()
            raise

    def close(self):
        self.pool.close()

    def metadata(self, key, default=None):
        with self.pool.connection() as conn:
            row = conn.execute("SELECT value FROM metadata WHERE key=%s", (key,)).fetchone()
        return json.loads(row["value"]) if row else default

    @property
    def revision(self): return self.metadata("revision", 0)

    @property
    def generation(self): return self.metadata("dataset_generation", 1)

    def events(self):
        generation = self.generation
        with self.pool.connection() as conn:
            rows = conn.execute("SELECT * FROM events WHERE dataset_generation=%s ORDER BY event_time,ingested_at,event_id", (generation,)).fetchall()
        return tuple(Event(**{**{k: row[k] for k in EVENT_COLUMNS}, "raw_json": json.loads(row["raw_json"])}) for row in rows)

    def holds(self):
        generation = self.generation
        with self.pool.connection() as conn:
            rows = conn.execute("SELECT * FROM held_events WHERE dataset_generation=%s", (generation,)).fetchall()
        return {r["event_id"]: (Event.model_validate_json(r["event_json"]), r["expires_at"], r["expired"]) for r in rows}

    def uploads(self, limit=20):
        with self.pool.connection() as conn:
            rows = conn.execute("SELECT dataset_generation,payload_json FROM event_uploads ORDER BY received_at DESC,batch_id DESC LIMIT %s", (limit,)).fetchall()
        return [{**json.loads(r["payload_json"]), "dataset_generation": r["dataset_generation"]} for r in rows]

    def set_metadata(self, key, value):
        """A value outside the event log (the stored reference kits); it does not change the publication revision."""
        with self.pool.connection() as conn:
            conn.execute("INSERT INTO metadata VALUES(%s,%s) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, json.dumps(value, sort_keys=True)))

    def commit_batch(self, events: list[Event], quarantined: list[tuple[str, str]], received_at=None, *, holds=None, stats=None, references=None, clock=None, upload=None, expected_revision: int | None = None, new_generation=False) -> int:
        """Commit in a few round trips; with expected_revision, refuse to write over another writer's commits.
        `new_generation` starts the next dataset generation in the same transaction (a reference kit switch)."""
        with self.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("SELECT key, value FROM metadata WHERE key IN ('revision','dataset_generation') FOR UPDATE")
            current = {r["key"]: json.loads(r["value"]) for r in cur.fetchall()}
            revision, generation = current["revision"], current["dataset_generation"]
            if expected_revision is not None and revision != expected_revision:
                raise StaleRevision(f"database revision {revision}, expected {expected_revision}")
            if new_generation:
                generation += 1
                cur.execute("UPDATE metadata SET value=%s WHERE key='dataset_generation'", (str(generation),))
            cur.executemany(f"INSERT INTO events(dataset_generation,{','.join(EVENT_COLUMNS)}) VALUES(%s{',%s' * len(EVENT_COLUMNS)})",
                            [(generation, *(json.dumps(e.raw_json, sort_keys=True) if c == "raw_json" else getattr(e, c) for c in EVENT_COLUMNS)) for e in events])
            cur.executemany("INSERT INTO quarantine(dataset_generation,received_at,reason,raw_json) VALUES(%s,%s,%s,%s)",
                            [(generation, received_at, reason, raw) for reason, raw in quarantined])
            if upload:
                cur.execute("INSERT INTO event_uploads VALUES(%s,%s,%s,%s)",
                            (upload["batch_id"], generation, received_at, json.dumps(upload, sort_keys=True)))
            if holds is not None:
                cur.execute("DELETE FROM held_events WHERE dataset_generation=%s", (generation,))
                cur.executemany("INSERT INTO held_events VALUES(%s,%s,%s,%s,%s)", [(generation, eid, e.model_dump_json(), deadline, expired) for eid, (e, deadline, expired) in holds.items()])
            updates = [(key, json.dumps(value, sort_keys=True)) for key, value in (("ingest_stats", stats), ("references", references), ("clock", clock)) if value is not None]
            updates.append(("revision", str(revision + 1)))
            cur.executemany("INSERT INTO metadata VALUES(%s,%s) ON CONFLICT(key) DO UPDATE SET value=excluded.value", updates)
        return revision + 1

    def reset(self) -> int:
        """Start a new dataset generation; nothing is deleted, earlier generations remain for audit."""
        with self.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("SELECT key, value FROM metadata WHERE key IN ('revision','dataset_generation') FOR UPDATE")
            current = {r["key"]: json.loads(r["value"]) for r in cur.fetchall()}
            cur.executemany("UPDATE metadata SET value=%s WHERE key=%s", [(str(current["revision"] + 1), "revision"),
                                                                          (str(current["dataset_generation"] + 1), "dataset_generation")])
            cur.execute("DELETE FROM metadata WHERE key='ingest_stats'")
        return current["revision"] + 1
