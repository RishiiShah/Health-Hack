"""Coordinator interventions on queue items [doc 5.1]: reassign (coordinator decides) and escalate (lead authorizes).

We record the decision and audit it; we never drive the production router [B p8]. Each command is one transaction
that writes the intervention and its audit row together, serialized with offer commands by the same advisory lock.
"""
import json
from datetime import datetime
from app.act.offers import OFFER_LOCK, OfferError
from app.db import pool

SCHEMA = (
    "SELECT pg_advisory_xact_lock(7310001)",
    "CREATE SEQUENCE IF NOT EXISTS intervention_seq",
    """CREATE TABLE IF NOT EXISTS interventions (
        id TEXT PRIMARY KEY DEFAULT 'INT-' || lpad(nextval('intervention_seq')::text, 5, '0'),
        item_id TEXT NOT NULL, kind TEXT NOT NULL CHECK (kind IN ('reassign','escalate')),
        consult_id TEXT, physician_id TEXT, state TEXT NOT NULL CHECK (state IN ('RECORDED','REQUESTED','AUTHORIZED')),
        created_at TIMESTAMPTZ NOT NULL, created_by TEXT NOT NULL, authorized_at TIMESTAMPTZ, authorized_by TEXT)""",
    "CREATE INDEX IF NOT EXISTS interventions_by_item ON interventions(item_id, id)",
    "ALTER TABLE interventions ADD COLUMN IF NOT EXISTS reason TEXT",
)


class InterventionLog:
    def __init__(self, url: str):
        self.pool = pool(url)
        self.version = 0
        with self.pool.connection() as conn, conn.transaction():
            for statement in SCHEMA:
                conn.execute(statement)

    def close(self):
        self.pool.close()

    def latest(self) -> dict[str, dict]:
        """Newest intervention per queue item, so the queue can show what was already done."""
        with self.pool.connection() as conn:
            rows = conn.execute("SELECT * FROM interventions ORDER BY id").fetchall()
        return {r["item_id"]: r for r in rows}

    def pending(self) -> list[dict]:
        """Escalations waiting for the lead, oldest first."""
        with self.pool.connection() as conn:
            return conn.execute("SELECT * FROM interventions WHERE state='REQUESTED' ORDER BY id").fetchall()

    def _audit(self, cur, at, item_id, actor, command, detail):
        cur.execute("INSERT INTO offer_audit(gap_id,at,actor,command,detail) VALUES(%s,%s,%s,%s,%s)",
                    (item_id, at, actor, command, json.dumps(detail, sort_keys=True, default=str)))

    def record(self, item, kind: str, physician_id: str | None, views, actor: str, at: datetime) -> dict:
        """`item`: the current queue item (validated by the caller to exist). Server-side checks, not the client's."""
        consult_id = item.where.get("consult_id")
        if kind == "reassign":
            if not consult_id:
                raise OfferError(422, "not_a_consult", "only a consult item can be reassigned")
            v = views.get(physician_id)
            if v is None or "off_shift" in v.exclusion_reasons or item.where["hospital_id"] not in v.allowed_hospitals:
                raise OfferError(422, "not_eligible", f"{physician_id} is not on shift and credentialed at {item.where['hospital_id']}")
            state = "RECORDED"
        elif kind == "escalate":
            state, physician_id = "REQUESTED", None
        else:
            raise OfferError(422, "unknown_kind", "kind must be reassign or escalate")
        with self.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(%s)", (OFFER_LOCK,))
            cur.execute("""INSERT INTO interventions(item_id,kind,consult_id,physician_id,state,created_at,created_by,reason)
                           VALUES(%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                        (item.id, kind, consult_id, physician_id, state, at, actor, f"{item.what}: {item.fix.reason}"))
            row = cur.fetchone()
            self._audit(cur, at, item.id, actor, kind, {"intervention": row["id"], "physician_id": physician_id, "recommended": item.fix.physician_id,
                                                        "followed_recommendation": physician_id == item.fix.physician_id if kind == "reassign" else None})
            self.version += 1
        return row

    def authorize(self, intervention_id: str, actor: str, at: datetime) -> dict:
        with self.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(%s)", (OFFER_LOCK,))
            cur.execute("SELECT * FROM interventions WHERE id=%s FOR UPDATE", (intervention_id,))
            row = cur.fetchone()
            if row is None:
                raise OfferError(404, "not_found", "no such intervention")
            if row["state"] != "REQUESTED":
                raise OfferError(409, "not_requested", f"intervention is {row['state']}")
            cur.execute("UPDATE interventions SET state='AUTHORIZED', authorized_at=%s, authorized_by=%s WHERE id=%s RETURNING *", (at, actor, intervention_id))
            row = cur.fetchone()
            self._audit(cur, at, row["item_id"], actor, "authorize", {"intervention": intervention_id})
            self.version += 1
        return row

    def reset(self):
        with self.pool.connection() as conn, conn.transaction():
            conn.execute("SELECT pg_advisory_xact_lock(%s)", (OFFER_LOCK,))
            conn.execute("TRUNCATE interventions")
            self.version += 1
