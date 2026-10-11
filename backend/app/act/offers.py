"""Step 8: split-shift offer state machine [doc 6]. Every command is one PostgreSQL transaction.

Atomicity: a global advisory lock serializes offer commands across instances, the offer row is locked FOR UPDATE,
and the transition, its audit row, any outbox message and the idempotency record commit together or not at all.
Rules are re-checked from current state inside the transaction; nothing trusts what was true when the button was shown.
Backstops in the schema: one open offer per physician (R7) and a trigger that rejects illegal transitions.
"""
import hashlib
import json
from dataclasses import dataclass
from threading import RLock
from datetime import datetime, timedelta
from typing import Callable
import psycopg
from psycopg.rows import dict_row
from app.clock import Clock, utc
from app.decide.eligibility import MIN_OFFER, OfferHistory, Proposal, evaluate_proposal
from app.engine.replay import State
from app.ops.coverage import SplitShift, remaining_need
from app.ops.detect import views_at
from app.ops.refs import ET, OpsRefs
from app.references import Refs

REPLY_WINDOW = timedelta(minutes=10)  # [B p2] offers expire; reply at exactly expires_at is late [A42]
OPEN = ("PROPOSED", "APPROVED", "SENT")
TRANSITIONS = {("PROPOSED", "APPROVED"), ("PROPOSED", "REJECTED"), ("PROPOSED", "CANCELLED"),
               ("APPROVED", "SENT"), ("APPROVED", "REJECTED"), ("APPROVED", "CANCELLED"),
               ("SENT", "ACCEPTED"), ("SENT", "ALREADY_FILLED"), ("SENT", "DECLINED"), ("SENT", "EXPIRED"), ("SENT", "WITHDRAWN")}
STATES = sorted({s for pair in TRANSITIONS for s in pair})
OFFER_LOCK = 7_310_002
SCHEMA = (
    "SELECT pg_advisory_xact_lock(7310001)",
    "CREATE SEQUENCE IF NOT EXISTS offer_seq",
    f"""CREATE TABLE IF NOT EXISTS offers (
        id TEXT PRIMARY KEY DEFAULT 'OFR-' || lpad(nextval('offer_seq')::text, 5, '0'),
        gap_id TEXT NOT NULL, physician_id TEXT NOT NULL, hospitals TEXT NOT NULL,
        start_at TIMESTAMPTZ NOT NULL, end_at TIMESTAMPTZ NOT NULL CHECK (end_at > start_at),
        state TEXT NOT NULL CHECK (state IN ({", ".join(f"'{s}'" for s in STATES)})),
        created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL, sent_at TIMESTAMPTZ, expires_at TIMESTAMPTZ,
        proposed_by TEXT NOT NULL, approved_by TEXT, reason TEXT, replaces TEXT)""",
    "CREATE UNIQUE INDEX IF NOT EXISTS one_open_offer_per_physician ON offers(physician_id) WHERE state IN ('PROPOSED','APPROVED','SENT')",
    """CREATE TABLE IF NOT EXISTS offer_audit (
        id BIGSERIAL PRIMARY KEY, offer_id TEXT, gap_id TEXT, at TIMESTAMPTZ NOT NULL, actor TEXT NOT NULL, command TEXT NOT NULL,
        from_state TEXT, to_state TEXT, revision INTEGER, detail TEXT NOT NULL)""",
    "CREATE INDEX IF NOT EXISTS offer_audit_by_gap ON offer_audit(gap_id, id)",
    """CREATE TABLE IF NOT EXISTS offer_outbox (
        id BIGSERIAL PRIMARY KEY, offer_id TEXT NOT NULL, physician_id TEXT NOT NULL, at TIMESTAMPTZ NOT NULL, kind TEXT NOT NULL, body TEXT NOT NULL)""",
    "CREATE TABLE IF NOT EXISTS offer_idempotency (key TEXT PRIMARY KEY, request TEXT NOT NULL, response TEXT NOT NULL)",
    f"""CREATE OR REPLACE FUNCTION offer_transition_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF (OLD.state, NEW.state) NOT IN ({", ".join(f"('{a}','{b}')" for a, b in sorted(TRANSITIONS))}) THEN
            RAISE EXCEPTION 'illegal offer transition % -> %', OLD.state, NEW.state;
          END IF;
          RETURN NEW;
        END $$""",
    "DROP TRIGGER IF EXISTS offer_transition_guard ON offers",
    "CREATE TRIGGER offer_transition_guard BEFORE UPDATE OF state ON offers FOR EACH ROW EXECUTE FUNCTION offer_transition_guard()",
)


class OfferError(Exception):
    """status: 404 not found (also another physician's offer), 409 conflict, 422 rule failed."""
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message

    def payload(self):
        return {"error": {"status": self.status, "code": self.code, "message": self.message}}


@dataclass(frozen=True)
class Context:
    """What the rules see: the published replay, references and the injected clock's now."""
    state: State
    refs: Refs
    ops: OpsRefs
    now: datetime
    revision: int = 0


@dataclass(frozen=True)
class Offer:
    id: str
    gap_id: str
    physician_id: str
    hospitals: tuple[str, ...]
    start: datetime
    end: datetime
    state: str
    created_at: datetime
    updated_at: datetime
    sent_at: datetime | None = None
    expires_at: datetime | None = None
    proposed_by: str = ""
    approved_by: str | None = None
    reason: str | None = None
    replaces: str | None = None

    def payload(self):
        return {k: v.isoformat() if isinstance(v, datetime) else list(v) if isinstance(v, tuple) else v for k, v in self.__dict__.items()}


def message(refs: Refs, hospitals, start: datetime, end: datetime, expires_at: datetime) -> str:
    """Typed fields only: hospital names, times, expiry and a fixed reason. No consult or patient data can reach it [B p4]."""
    names = ", ".join(refs.hospitals[h].name for h in hospitals)
    t = lambda x: x.astimezone(ET).strftime("%-I:%M %p")
    minutes = int((end - start).total_seconds() // 60)
    length = f"{minutes // 60} h" + (f" {minutes % 60} min" if minutes % 60 else "")
    return (f"Sevaro split-shift offer. {names}. {t(start)} to {t(end)} Eastern ({length}). "
            f"Requested because of a coverage gap at a hospital you are credentialed for. Expires at {t(expires_at)}.")


def notice(refs: Refs, hospitals, start: datetime, end: datetime) -> str:
    names = ", ".join(refs.hospitals[h].name for h in hospitals)
    return f"Sevaro split-shift offer for {names}, {start.astimezone(ET):%-I:%M %p} to {end.astimezone(ET):%-I:%M %p} Eastern, is no longer needed. Thank you."


def _row(r) -> Offer:
    return Offer(r["id"], r["gap_id"], r["physician_id"], tuple(json.loads(r["hospitals"])), r["start_at"], r["end_at"], r["state"],
                 r["created_at"], r["updated_at"], r["sent_at"], r["expires_at"], r["proposed_by"], r["approved_by"], r["reason"], r["replaces"])


class OfferDesk:
    """Offer commands. `context()` returns the current Context; call it under the ingest coordinator's lock so a
    command sees exactly one revision. `base_history` is the supplied offer history (offers made outside this tool)."""

    def __init__(self, url: str, context: Callable[[], Context], base_history: OfferHistory = OfferHistory()):
        self.url, self.context, self.base_history = url, context, base_history
        self.lock = RLock()  # one connection is shared by the API's worker threads: one command or read at a time
        self.version = 0  # bumps on every committed command, so cached snapshots know offers changed
        self.conn = self._connect()
        with self.conn.transaction():
            for statement in SCHEMA:
                self.conn.execute(statement)

    def _connect(self):
        return psycopg.connect(self.url, autocommit=True, row_factory=dict_row, options="-c timezone=UTC")

    # ---- reads -------------------------------------------------------------------------------------------
    def offers(self, physician_id: str | None = None) -> list[Offer]:
        with self.lock:
            rows = self.conn.execute("SELECT * FROM offers WHERE %s::text IS NULL OR physician_id=%s ORDER BY id", (physician_id, physician_id)).fetchall()
        return [_row(r) for r in rows]

    def offer(self, offer_id: str, physician_id: str | None = None) -> Offer:
        with self.lock:
            r = self.conn.execute("SELECT * FROM offers WHERE id=%s", (offer_id,)).fetchone()
        if r is None or (physician_id is not None and r["physician_id"] != physician_id):
            raise OfferError(404, "not_found", "no such offer")  # another physician's offer is indistinguishable from none
        return _row(r)

    def audit(self, gap_id: str | None = None) -> list[dict]:
        with self.lock:
            rows = self.conn.execute("SELECT * FROM offer_audit WHERE %s::text IS NULL OR gap_id=%s ORDER BY id", (gap_id, gap_id)).fetchall()
        return [{**r, "detail": json.loads(r["detail"])} for r in rows]

    def outbox(self) -> list[dict]:
        with self.lock:
            return self.conn.execute("SELECT * FROM offer_outbox ORDER BY id").fetchall()

    def accepted(self) -> tuple:
        """Accepted split shifts, as decide()/project() take them."""
        return self._accepted(self.offers())

    def history(self, now: datetime, exclude: str | None = None) -> OfferHistory:
        """R7/R8 and accepted hours from our own offers, plus the supplied history. `exclude`: the offer being re-checked."""
        return self._history(self.offers(), now, exclude)

    def _history(self, offers, now, exclude=None):
        base = self.base_history
        sent = dict(base.sent_7d)
        for o in offers:
            if o.sent_at and now - timedelta(days=7) <= o.sent_at <= now:
                sent[o.physician_id] = sent.get(o.physician_id, 0) + 1
        accepted = {}
        for o in offers:
            if o.state == "ACCEPTED":
                accepted.setdefault(o.physician_id, []).append((o.start, o.end))
        open_ = set(base.open) | {o.physician_id for o in offers if o.state in OPEN and o.id != exclude}
        return OfferHistory(frozenset(open_), sent, {p: tuple(w) for p, w in accepted.items()}, base.supplied or bool(offers))

    # ---- transaction plumbing ----------------------------------------------------------------------------
    def _run(self, command: str, actor: str, args: dict, idempotency_key: str | None, body):
        """One command = one transaction. A refused command still commits its audit row, then raises; with an
        idempotency key the same request returns the same result (or the same refusal) forever."""
        with self.lock:
            try:
                return self._run_locked(command, actor, args, idempotency_key, body)
            finally:
                self.version += 1

    def _run_locked(self, command, actor, args, idempotency_key, body):
        if self.conn.broken:
            self.conn = self._connect()
        request = json.dumps({"command": command, "actor": actor, **args}, sort_keys=True, default=str)
        error = None
        with self.conn.transaction(), self.conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(%s)", (OFFER_LOCK,))
            if idempotency_key:
                cur.execute("SELECT request, response FROM offer_idempotency WHERE key=%s", (idempotency_key,))
                stored = cur.fetchone()
                if stored:
                    if stored["request"] != request:
                        raise OfferError(409, "idempotency_key_reused", "this Idempotency-Key was used for a different request")
                    response = json.loads(stored["response"])
                    if "error" in response:
                        e = response["error"]
                        raise OfferError(e["status"], e["code"], e["message"])
                    return response
            ctx = self.context()
            ctx = Context(ctx.state, ctx.refs, ctx.ops, utc(ctx.now), ctx.revision)
            try:
                response = body(cur, ctx)
            except OfferError as exc:
                error, response = exc, exc.payload()
                gap_id = args.get("gap_id")
                if gap_id is None and args.get("offer_id"):
                    cur.execute("SELECT gap_id FROM offers WHERE id=%s", (args["offer_id"],))
                    gap_id = (cur.fetchone() or {}).get("gap_id")  # so the gap's audit trail shows refused replies too
                self._audit(cur, ctx, args.get("offer_id"), gap_id, actor, command + ":refused", None, None, {"code": exc.code, "message": exc.message, **args})
            if idempotency_key:
                cur.execute("INSERT INTO offer_idempotency VALUES(%s,%s,%s)", (idempotency_key, request, json.dumps(response, default=str)))
        if error:
            raise error
        return response

    def _audit(self, cur, ctx, offer_id, gap_id, actor, command, from_state, to_state, detail):
        cur.execute("INSERT INTO offer_audit(offer_id,gap_id,at,actor,command,from_state,to_state,revision,detail) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (offer_id, gap_id, ctx.now, actor, command, from_state, to_state, ctx.revision, json.dumps(detail, sort_keys=True, default=str)))

    def _lock(self, cur, ctx, offer_id, physician_id=None) -> Offer:
        cur.execute("SELECT * FROM offers WHERE id=%s FOR UPDATE", (offer_id,))
        r = cur.fetchone()
        if r is None or (physician_id is not None and r["physician_id"] != physician_id):
            raise OfferError(404, "not_found", "no such offer")
        offer = _row(r)
        if ctx.now < offer.updated_at:
            raise OfferError(409, "clock_rewound", f"clock {ctx.now.isoformat()} is before this offer's last change {offer.updated_at.isoformat()}")  # [A43]
        return offer

    def _move(self, cur, ctx, offer: Offer, to: str, actor: str, command: str, detail: dict, **fields) -> Offer:
        assert (offer.state, to) in TRANSITIONS, (offer.state, to)
        sets = {"state": to, "updated_at": ctx.now, **fields}
        cur.execute(f"UPDATE offers SET {', '.join(f'{k}=%s' for k in sets)} WHERE id=%s RETURNING *", (*sets.values(), offer.id))
        moved = _row(cur.fetchone())
        self._audit(cur, ctx, offer.id, offer.gap_id, actor, command, offer.state, to, detail)
        return moved

    def _all(self, cur):
        cur.execute("SELECT * FROM offers ORDER BY id")
        return [_row(r) for r in cur.fetchall()]

    # ---- rule checks (from current state, inside the transaction) ----------------------------------------
    def _accepted(self, offers, without=None):
        return tuple(SplitShift(o.physician_id, o.start, o.end, frozenset(o.hospitals), o.updated_at)
                     for o in offers if o.state == "ACCEPTED" and o.id != without)

    def _need(self, ctx, offers, hospitals, start, end, extra=()):
        views = views_at(ctx.state, ctx.refs, ctx.now)
        return remaining_need(ctx.state, ctx.refs, ctx.ops, views, ctx.now, (*self._accepted(offers), *extra), hospitals, start, end)

    def _check(self, ctx, offers, physician_id, hospitals, start, end, exclude=None, every_hospital=True):
        """Every eligibility rule for this physician and window, and the offer must still be needed (at every offered
        hospital when proposing; at any of them on later re-checks). Returns the reason it fails, or None."""
        candidate = next((c for c in evaluate_proposal(Proposal(start, end, tuple(hospitals)), ctx.refs, ctx.ops, ctx.now,
                                                       self._history(offers, ctx.now, exclude)) if c.physician_id == physician_id), None)
        if candidate is None:
            return {"code": "not_on_roster", "message": f"{physician_id} is not an off-shift roster physician"}
        if not candidate.eligible:
            return {"code": "ineligible", "message": f"{physician_id} fails " + ", ".join(f"{r.key} ({r.value})" for r in candidate.rules if not r.passed),
                    "failed": list(candidate.failed)}
        if set(hospitals) - set(candidate.hospitals):
            return {"code": "not_credentialed", "message": f"{physician_id} is not credentialed at {sorted(set(hospitals) - set(candidate.hospitals))}"}
        need = self._need(ctx, offers, hospitals, candidate.ready_at, end)
        if not any(need.values()):
            return {"code": "gap_filled", "message": "no remaining need at the offered hospitals in this window", "need": need}
        if every_hospital and not all(need.values()):
            # Trap guard and message rule: an offer names only hospitals that need help.
            return {"code": "non_gap_hospital", "message": f"no need at {sorted(h for h, n in need.items() if not n)}", "need": need}
        return None

    def reset(self, actor: str, at: datetime):
        """Admin reset for a fresh demo run: open and past offers go; the audit log is append-only and keeps a reset row."""
        with self.lock, self.conn.transaction(), self.conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(%s)", (OFFER_LOCK,))
            cur.execute("TRUNCATE offers, offer_outbox, offer_idempotency")
            cur.execute("INSERT INTO offer_audit(at,actor,command,detail) VALUES(%s,%s,'reset','{}')", (at, actor))
            self.version += 1

    # ---- commands ----------------------------------------------------------------------------------------
    def propose(self, gap_id: str, physician_id: str, start: datetime, end: datetime, hospitals, actor: str, idempotency_key=None, replaces=None):
        """`hospitals` may be a callable that picks them from current decisions. It runs after the idempotency check,
        so a retried request returns its stored result even though the queue has changed since the first try."""
        start, end = utc(start), utc(end)
        args = {"gap_id": gap_id, "physician_id": physician_id, "start": start, "end": end,
                "hospitals": "default" if callable(hospitals) else tuple(sorted(set(hospitals)))}

        def body(cur, ctx):
            hospitals_ = tuple(sorted(set(hospitals() if callable(hospitals) else hospitals)))
            if start < ctx.now:
                raise OfferError(422, "start_in_past", "an offer cannot start in the past")
            failure = self._check(ctx, self._all(cur), physician_id, hospitals_, start, end)
            if failure:
                raise OfferError(409 if failure["code"] == "gap_filled" else 422, failure["code"], failure["message"])
            return self._insert(cur, ctx, gap_id, physician_id, hospitals_, start, end, actor, replaces).payload()
        return self._run("propose", actor, args, idempotency_key, body)

    def _insert(self, cur, ctx, gap_id, physician_id, hospitals, start, end, actor, replaces=None) -> Offer:
        try:
            with cur.connection.transaction():  # savepoint: a unique-index hit leaves the outer transaction usable
                cur.execute("""INSERT INTO offers(gap_id,physician_id,hospitals,start_at,end_at,state,created_at,updated_at,proposed_by,replaces)
                               VALUES(%s,%s,%s,%s,%s,'PROPOSED',%s,%s,%s,%s) RETURNING *""",
                            (gap_id, physician_id, json.dumps(list(hospitals)), start, end, ctx.now, ctx.now, actor, replaces))
        except psycopg.errors.UniqueViolation:
            raise OfferError(409, "open_offer_exists", f"{physician_id} already has an open offer (R7)")
        offer = _row(cur.fetchone())
        self._audit(cur, ctx, offer.id, gap_id, actor, "propose", None, "PROPOSED",
                    {"physician_id": physician_id, "hospitals": list(hospitals), "start": start, "end": end, "replaces": replaces})
        return offer

    def approve(self, offer_id: str, actor: str, idempotency_key=None):
        """Approve and send in one call (API contract), each step re-checked; a failed check cancels with the reason."""
        def body(cur, ctx):
            offer = self._lock(cur, ctx, offer_id)
            if offer.state != "PROPOSED":
                raise OfferError(409, "not_proposed", f"offer is {offer.state}")
            start = max(offer.start, ctx.now)  # approved late: the window starts now, and R6 is re-checked on what is left
            failure = self._check(ctx, self._all(cur), offer.physician_id, offer.hospitals, start, offer.end, exclude=offer.id, every_hospital=False)
            if failure:
                return self._move(cur, ctx, offer, "CANCELLED", actor, "approve:recheck_failed", failure, reason=failure["message"]).payload()
            approved = self._move(cur, ctx, offer, "APPROVED", actor, "approve", {"approver": actor}, approved_by=actor)
            expires = ctx.now + REPLY_WINDOW
            sent = self._move(cur, ctx, approved, "SENT", actor, "send", {"expires_at": expires, "start": start, "start_moved": start != offer.start},
                              sent_at=ctx.now, expires_at=expires, start_at=start)
            cur.execute("INSERT INTO offer_outbox(offer_id,physician_id,at,kind,body) VALUES(%s,%s,%s,'offer',%s)",
                        (sent.id, sent.physician_id, ctx.now, message(ctx.refs, sent.hospitals, sent.start, sent.end, expires)))
            return sent.payload()
        return self._run("approve", actor, {"offer_id": offer_id}, idempotency_key, body)

    def reject(self, offer_id: str, actor: str, reason: str, idempotency_key=None):
        def body(cur, ctx):
            offer = self._lock(cur, ctx, offer_id)
            if offer.state not in {"PROPOSED", "APPROVED"}:
                raise OfferError(409, "not_pending", f"offer is {offer.state}")
            return self._move(cur, ctx, offer, "REJECTED", actor, "reject", {"reason": reason}, reason=reason).payload()
        return self._run("reject", actor, {"offer_id": offer_id, "reason": reason}, idempotency_key, body)

    def accept(self, offer_id: str, physician_id: str, idempotency_key=None):
        return self._reply(offer_id, physician_id, "accept", idempotency_key)

    def decline(self, offer_id: str, physician_id: str, idempotency_key=None):
        return self._reply(offer_id, physician_id, "decline", idempotency_key)

    def _reply(self, offer_id, physician_id, command, idempotency_key):
        actor = f"physician:{physician_id}"

        def body(cur, ctx):
            offer = self._lock(cur, ctx, offer_id, physician_id)
            done = {"accept": {"ACCEPTED"}, "decline": {"DECLINED"}}[command]
            if offer.state in done:
                return offer.payload()  # the same reply again: same answer, nothing changes
            if offer.state == "SENT" and ctx.now >= offer.expires_at:
                self._expire(cur, ctx, offer)  # materialize, then refuse; the expiry and its follow-up commit
                raise OfferError(409, "expired", "the reply window closed")
            if offer.state != "SENT":
                code = {"WITHDRAWN": "already_filled", "ALREADY_FILLED": "already_filled", "EXPIRED": "expired"}.get(offer.state, "conflicting_reply")
                raise OfferError(409, code, f"offer is {offer.state}")
            if command == "decline":
                declined = self._move(cur, ctx, offer, "DECLINED", actor, "decline", {})
                self._next_candidate(cur, ctx, declined)
                return declined.payload()
            offers = self._all(cur)
            need = self._need(ctx, offers, offer.hospitals, max(offer.start, ctx.now), offer.end)
            if not any(need.values()):
                filled = self._move(cur, ctx, offer, "ALREADY_FILLED", actor, "accept:already_filled", {"need": need})
                cur.execute("INSERT INTO offer_outbox(offer_id,physician_id,at,kind,body) VALUES(%s,%s,%s,'notice',%s)",
                            (offer.id, offer.physician_id, ctx.now, notice(ctx.refs, offer.hospitals, offer.start, offer.end)))
                return filled.payload()
            accepted = self._move(cur, ctx, offer, "ACCEPTED", actor, "accept", {"need_before": need})
            self._close_unneeded(cur, ctx)
            return accepted.payload()
        return self._run(command, actor, {"offer_id": offer_id}, idempotency_key, body)

    def _expire(self, cur, ctx, offer):
        expired = self._move(cur, ctx, offer, "EXPIRED", "system", "expire", {"expires_at": offer.expires_at})
        self._next_candidate(cur, ctx, expired)

    def _close_unneeded(self, cur, ctx):
        """Stop asking once the gap is filled: open offers that no longer reduce any need are withdrawn or cancelled."""
        for o in self._all(cur):
            if o.state not in OPEN:
                continue
            if any(self._need(ctx, self._all(cur), o.hospitals, max(o.start, ctx.now), o.end).values()):
                continue
            if o.state == "SENT":
                self._move(cur, ctx, o, "WITHDRAWN", "system", "withdraw", {"reason": "gap filled"}, reason="gap filled")
                cur.execute("INSERT INTO offer_outbox(offer_id,physician_id,at,kind,body) VALUES(%s,%s,%s,'notice',%s)",
                            (o.id, o.physician_id, ctx.now, notice(ctx.refs, o.hospitals, o.start, o.end)))
            else:
                self._move(cur, ctx, o, "CANCELLED", "system", "cancel", {"reason": "gap filled"}, reason="gap filled")

    def _next_candidate(self, cur, ctx, ended: Offer):
        """After a decline or expiry: propose the next-ranked eligible physician for what is still needed.
        It is only PROPOSED; the lead still approves it [B p2]. Physicians already asked for this gap are skipped."""
        offers = self._all(cur)
        asked = {o.physician_id for o in offers if o.gap_id == ended.gap_id}
        start = max(ended.start, ctx.now)
        end = max(ended.end, start + MIN_OFFER)
        need = self._need(ctx, offers, ended.hospitals, start, end)
        hospitals = tuple(h for h in ended.hospitals if need[h])
        if not hospitals:
            self._audit(cur, ctx, ended.id, ended.gap_id, "system", "next_candidate:none", None, None, {"reason": "gap filled"})
            return None
        ranked = evaluate_proposal(Proposal(start, end, hospitals), ctx.refs, ctx.ops, ctx.now, self._history(offers, ctx.now))
        for c in ranked:
            if c.eligible and c.physician_id not in asked and set(c.hospitals) == set(hospitals) and \
                    self._check(ctx, offers, c.physician_id, hospitals, start, end) is None:  # hospitals all still need help
                return self._insert(cur, ctx, ended.gap_id, c.physician_id, hospitals, start, end, "system", replaces=ended.id)
        self._audit(cur, ctx, ended.id, ended.gap_id, "system", "next_candidate:none", None, None,
                    {"reason": "no other eligible physician; escalate", "candidates": {c.physician_id: list(c.failed) for c in ranked}})
        return None

    def sweep(self, idempotency_key=None):
        """Lazy timers made durable: expire overdue offers, withdraw or cancel offers whose gap closed by other means."""
        def body(cur, ctx):
            changed = []
            for o in self._all(cur):
                if o.state == "SENT" and ctx.now >= o.expires_at:
                    self._expire(cur, ctx, o)
                    changed.append(o.id)
            before = {o.id: o.state for o in self._all(cur)}
            self._close_unneeded(cur, ctx)
            changed += [o.id for o in self._all(cur) if before.get(o.id) not in (None, o.state)]
            return {"changed": changed}
        return self._run("sweep", "system", {}, idempotency_key, body)
