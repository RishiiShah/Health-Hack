import json, sqlite3
from pathlib import Path
from app.models import Event

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=FULL;
CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS events (dataset_generation INTEGER NOT NULL, event_id TEXT NOT NULL, event_time TEXT NOT NULL, ingested_at TEXT NOT NULL, received_at TEXT NOT NULL, event_type TEXT NOT NULL, consult_id TEXT, physician_id TEXT, hospital_id TEXT, consult_type TEXT, value TEXT, source TEXT NOT NULL, time_offset TEXT, raw_json TEXT NOT NULL, adapter_version TEXT NOT NULL, PRIMARY KEY(dataset_generation,event_id));
CREATE INDEX IF NOT EXISTS events_by_time ON events(dataset_generation,event_time,ingested_at,event_id);
CREATE TABLE IF NOT EXISTS quarantine (id INTEGER PRIMARY KEY, dataset_generation INTEGER NOT NULL, received_at TEXT NOT NULL, reason TEXT NOT NULL, raw_json TEXT NOT NULL);
"""

class EventDatabase:
    def __init__(self, path: str):
        self.path = path
        if path != ":memory:": Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False, timeout=5)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.execute("INSERT OR IGNORE INTO metadata VALUES('revision','0')")
        self.conn.execute("INSERT OR IGNORE INTO metadata VALUES('dataset_generation','1')")
        self.conn.commit()
    @property
    def revision(self): return int(self.conn.execute("SELECT value FROM metadata WHERE key='revision'").fetchone()[0])
    @property
    def generation(self): return int(self.conn.execute("SELECT value FROM metadata WHERE key='dataset_generation'").fetchone()[0])
    def events(self):
        rows = self.conn.execute("SELECT * FROM events WHERE dataset_generation=? ORDER BY event_time,ingested_at,event_id", (self.generation,)).fetchall()
        return tuple(Event(**{**dict(row), "raw_json":json.loads(row["raw_json"])}) for row in rows)
    def commit_batch(self, events: list[Event], quarantined: list[tuple[str,str]], received_at: str = "") -> int:
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            generation = self.generation
            for e in events:
                values = e.model_dump(mode="json")
                for column in ("event_time", "ingested_at", "received_at"):
                    values[column] = getattr(e, column).isoformat(timespec="microseconds")
                values["raw_json"] = json.dumps(e.raw_json, sort_keys=True)
                cols = list(values)
                self.conn.execute(f"INSERT INTO events(dataset_generation,{','.join(cols)}) VALUES({','.join('?' for _ in range(len(cols)+1))})", [generation]+[values[c] for c in cols])
            for reason, raw in quarantined:
                self.conn.execute("INSERT INTO quarantine(dataset_generation,received_at,reason,raw_json) VALUES(?,?,?,?)", (generation, received_at, reason, raw))
            revision = self.revision + 1
            self.conn.execute("UPDATE metadata SET value=? WHERE key='revision'", (str(revision),))
            self.conn.commit()
            return revision
        except Exception:
            self.conn.rollback(); raise
