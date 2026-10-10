import asyncio
import csv
import io
import json
import logging
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from uuid import uuid4
from fastapi import Body, Depends, FastAPI, Header, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool
from app.act.interventions import InterventionLog
from app.act.offers import OfferDesk, OfferError, message
from app.auth import Auth, Principal
from app.clock import AnchoredClock, FixedClock, ServerReceiptClock, make_clock, utc
from app.config import settings
from app.coordinator import MutationCoordinator
from app.db import EventDatabase
from app.ingest.adapters import FIXTURE_VERSION
from app.models import EventInput
from app.service import Engine, base_history, candidate_payload, jsonable, load_references
from app.tts import Speech

log = logging.getLogger(__name__)
WALL = ServerReceiptClock()  # token expiry is real time, never the simulation clock
ALERT_REASONS = {"unassigned": "a consult has no physician", "stranded": "a consult is held by a physician who cannot act",
                 "escalate": "consults are waiting with nobody credentialed free", "handoff_needed": "a consult needs a handoff before shift end",
                 "stage_breach": "a consult has passed its time limit", "now_gap": "a hospital is short of credentialed coverage now",
                 "gap": "a hospital will be short of credentialed coverage", "notes_at_shift_end": "open notes near shift end",
                 "note_overdue": "a note is overdue", "surge": "demand is above normal"}


class OfferRequest(BaseModel):
    gap_id: str
    physician_id: str
    start: datetime
    end: datetime
    hospitals: list[str] | None = None  # default: the hospitals the engine's candidate covers for this gap


class InterventionRequest(BaseModel):
    kind: str
    item_id: str
    physician_id: str | None = None


class ClockRequest(BaseModel):
    mode: str  # fixed | anchored (moves forward in real time from `at`)
    at: datetime


def bearer(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    return header[7:].strip() if header.lower().startswith("bearer ") else None


def need(*permissions):
    """The server checks every request; hiding a button in a client is not security [00-Boundaries]."""
    def check(request: Request) -> Principal:
        who = request.app.state.auth.identify(bearer(request), WALL.now())
        if who is None:
            raise HTTPException(401, "missing, wrong or expired token")
        if not set(permissions) & set(who.permissions):
            raise HTTPException(403, "this role may not do that")
        return who
    return Depends(check)


def create_app(database_url: str | None = None, test_clock=None, *, auth: Auth | None = None, references=None, history_path=None,
               speech: Speech | None = None, sweep_s: float | None = None) -> FastAPI:
    epoch = str(uuid4())
    # Readers within the same second share one encoding. Any commit, newly visible event or offer change
    # (a new key) re-encodes at once; only clock-derived fields may lag by <1 s.
    snapshot_cache = [(None, b"")]
    url = database_url or settings.database_url

    @asynccontextmanager
    async def lifespan(api: FastAPI):
        db = EventDatabase(url)
        task, conns = None, [db.conn]
        try:
            events = db.events()
            clock = test_clock or make_clock(settings.clock_mode, settings.fixed_datetime(), max((e.event_time for e in events), default=None))
            refs, ops = references or startup_references()
            coordinator = MutationCoordinator(db, clock, settings.late_lag_s, refs=refs, orphan_hold_s=settings.orphan_hold_s)
            engine = Engine(coordinator, ops, None, InterventionLog(url))
            conns.append(engine.interventions.conn)
            engine.desk = OfferDesk(url, engine.context, base_history(history_path or settings.offer_history, clock.now()))
            api.state.db, api.state.clock, api.state.coordinator, api.state.engine = db, clock, coordinator, engine
            api.state.auth = auth or Auth(settings.coordinator_token, settings.lead_token, settings.admin_token, settings.lead_name, settings.token_secret)
            api.state.speech = speech or Speech(url)
            conns += [engine.desk.conn, api.state.speech.conn]
            interval = settings.sweep_s if sweep_s is None else sweep_s
            if interval > 0:
                task = asyncio.create_task(sweeper(api, interval))
            yield
        finally:
            if task:
                task.cancel()
            for conn in conns:
                conn.close()

    def startup_references():
        directory = settings.reference_dir
        if not directory or not (Path(directory) / "hospitals.csv").exists():
            # Loud, not fatal: /ready reports detection unavailable and decision routes answer 503.
            log.warning("no reference files at CC_DATA_DIR=%r; decisions are unavailable until they are provided", directory)
            return None, None
        return load_references(directory, date.fromisoformat(settings.service_date) if settings.service_date else None)

    async def sweeper(api, interval):
        while True:
            await asyncio.sleep(interval)
            try:
                await run_in_threadpool(sweep, api)
            except Exception:
                log.exception("sweep failed; retrying next interval")  # never silent, never fatal

    def sweep(api):
        api.state.coordinator.sweep()
        if api.state.engine.ready:
            api.state.engine.desk.sweep()

    api = FastAPI(title="Sevaro Command Center API", version="0.2.0", lifespan=lifespan)

    @api.exception_handler(OfferError)
    def offer_error(request: Request, exc: OfferError):
        return JSONResponse(exc.payload(), status_code=exc.status)

    def engine_of(request) -> Engine:
        engine = request.app.state.engine
        if not engine.ready:
            raise HTTPException(503, "reference data not loaded (set CC_DATA_DIR)")
        return engine

    def gap_item(request, item_id):
        item = engine_of(request).item(item_id)
        if item is None:
            raise HTTPException(404, "no such item in the current queue")
        return item

    @api.get("/health")
    def health(): return {"status": "ok"}

    @api.get("/ready")
    def ready(request: Request):
        p = request.app.state.coordinator.published
        decisions = request.app.state.engine.ready
        return {"ready": True, "revision": p.revision, "event_count": p.event_count, "clock_mode": request.app.state.clock.mode,
                "capabilities": {"event_ingest": True, "durable_event_log": True, "consult_replay": True, "fixture_adapter": True,
                                 "orphan_holding": True, "reference_validation": p.refs is not None, "physician_state": decisions, "detection": decisions,
                                 "coverage_forecast": decisions, "offers": decisions, "websocket": True, "authentication": True,
                                 "speech": request.app.state.speech.available}}

    @api.get("/me")
    def me(who: Principal = need("ops.view", "offers.view_own", "admin.inject")):
        return who.payload()

    # ---- events (admin) ----------------------------------------------------------------------------------
    @api.post("/events")
    def ingest(request: Request, payload: EventInput | list[EventInput], who: Principal = need("admin.inject")):
        rows = payload if isinstance(payload, list) else [payload]
        if len(rows) > settings.max_batch_rows: raise HTTPException(413, "batch exceeds configured row limit")
        report = request.app.state.coordinator.ingest(rows)
        if report["unresolved"]:
            report["capability_warning"] = "Unresolved events remain held until dependencies arrive or the server-time deadline expires."
        return report

    @api.post("/events/csv")
    async def ingest_csv(request: Request, who: Principal = need("admin.inject")):
        """The judges' file: same columns as event_stream.csv, appended without restart [H ch4]."""
        text = (await request.body()).decode("utf-8-sig")
        rows = list(csv.DictReader(io.StringIO(text)))
        if len(rows) > settings.max_batch_rows: raise HTTPException(413, "batch exceeds configured row limit")
        return await run_in_threadpool(request.app.state.coordinator.ingest_raw, rows, FIXTURE_VERSION)

    # ---- snapshot ----------------------------------------------------------------------------------------
    def snapshot_bytes(app) -> bytes:
        engine, coordinator = app.state.engine, app.state.coordinator
        p = coordinator.current_publication()
        key = (p.revision, id(p.state), p.as_of.replace(microsecond=0), engine.desk.version, engine.interventions.version)
        if snapshot_cache[0][0] != key:
            snapshot_cache[0] = (key, json.dumps(engine.snapshot(epoch, app.state.clock.mode), separators=(",", ":")).encode())
        return snapshot_cache[0][1]

    @api.get("/snapshot")
    def snapshot(request: Request, who: Principal = need("ops.view")):
        return Response(snapshot_bytes(request.app), media_type="application/json")

    @api.websocket("/ws")
    async def ws(websocket: WebSocket, token: str | None = None):
        """Whole snapshot on every change, never partial updates. Browsers cannot set headers, so the token is a query parameter."""
        who = websocket.app.state.auth.identify(token, WALL.now())
        if who is None or "ops.view" not in who.permissions:
            await websocket.close(code=1008)
            return
        await websocket.accept()
        seq, last = 0, None
        try:
            while True:
                body = await run_in_threadpool(snapshot_bytes, websocket.app)
                if body != last:
                    seq, last = seq + 1, body
                    await websocket.send_text(f'{{"epoch":"{epoch}","seq":{seq},"snapshot":{body.decode()}}}')
                await asyncio.sleep(1)
        except WebSocketDisconnect:
            return

    @api.get("/consults/{consult_id}")
    def consult(consult_id: str, request: Request, who: Principal = need("ops.view")):
        c = request.app.state.coordinator.current_publication().state.consults.get(consult_id)
        if c is None: raise HTTPException(404, "consult not found")
        return {"consult_id": c.consult_id, "stage": c.stage, "owner": c.owner, "history": [{"stage": s, "at": t.isoformat()} for s, t in c.history]}

    # ---- decide ------------------------------------------------------------------------------------------
    @api.get("/gaps/{gap_id:path}/candidates")
    def candidates(gap_id: str, request: Request, who: Principal = need("ops.view")):
        item = gap_item(request, gap_id)
        if not item.candidates:
            raise HTTPException(404, "this item has no candidate table")
        return {"gap_id": item.id, "fix": item.fix.kind, "candidates": [candidate_payload(c) for c in item.candidates]}

    @api.get("/gaps/{gap_id:path}/trap-check")
    def trap(gap_id: str, request: Request, who: Principal = need("ops.view")):
        item = gap_item(request, gap_id)
        if item.fix.kind != "split_shift":
            raise HTTPException(409, "the fix for this item is not a split-shift offer")
        return {"gap_id": item.id, **engine_of(request).trap(item)}

    @api.post("/interventions")
    def intervene(body: InterventionRequest, request: Request, who: Principal = need("ops.intervene")):
        engine = engine_of(request)
        item = gap_item(request, body.item_id)
        _, d = engine.decisions()
        return jsonable(engine.interventions.record(item, body.kind, body.physician_id, d.views, who.display_name, engine.context().now))

    @api.post("/interventions/{intervention_id}/authorize")
    def authorize(intervention_id: str, request: Request, who: Principal = need("approvals.decide")):
        engine = engine_of(request)
        return jsonable(engine.interventions.authorize(intervention_id, who.display_name, engine.context().now))

    # ---- act: offers -------------------------------------------------------------------------------------
    @api.post("/offers")
    def propose(body: OfferRequest, request: Request, who: Principal = need("ops.intervene"), idempotency_key: str | None = Header(None)):
        engine = engine_of(request)

        def candidate_hospitals():
            item = engine.item(body.gap_id)
            c = next((c for c in item.candidates if c.physician_id == body.physician_id), None) if item else None
            if c is None:
                raise OfferError(422, "not_a_candidate", "this physician is not a candidate for this gap in the current queue")
            return c.hospitals
        return engine.desk.propose(body.gap_id, body.physician_id, utc(body.start), utc(body.end), body.hospitals or candidate_hospitals,
                                   who.display_name, idempotency_key)

    @api.post("/offers/{offer_id}/approve")
    def approve(offer_id: str, request: Request, who: Principal = need("approvals.decide"), idempotency_key: str | None = Header(None)):
        return engine_of(request).desk.approve(offer_id, who.display_name, idempotency_key)

    @api.post("/offers/{offer_id}/reject")
    def reject(offer_id: str, request: Request, reason: str = Body(..., embed=True), who: Principal = need("approvals.decide"),
               idempotency_key: str | None = Header(None)):
        return engine_of(request).desk.reject(offer_id, who.display_name, reason, idempotency_key)

    @api.get("/offers")
    def offers(request: Request, who: Principal = need("offers.view_all", "offers.view_own")):
        return [o.payload() for o in engine_of(request).desk.offers(who.physician_id)]  # a physician sees only their own

    @api.get("/offers/{offer_id}")
    def offer(offer_id: str, request: Request, who: Principal = need("offers.view_all", "offers.view_own")):
        return engine_of(request).desk.offer(offer_id, who.physician_id).payload()

    @api.post("/offers/{offer_id}/accept")
    def accept(offer_id: str, request: Request, who: Principal = need("offers.respond"), idempotency_key: str | None = Header(None)):
        return engine_of(request).desk.accept(offer_id, who.physician_id, idempotency_key)

    @api.post("/offers/{offer_id}/decline")
    def decline(offer_id: str, request: Request, who: Principal = need("offers.respond"), idempotency_key: str | None = Header(None)):
        return engine_of(request).desk.decline(offer_id, who.physician_id, idempotency_key)

    @api.get("/offers/{offer_id}/audio")
    def offer_audio(offer_id: str, request: Request, who: Principal = need("approvals.decide", "offers.view_own")):
        engine = engine_of(request)
        o = engine.desk.offer(offer_id, who.physician_id)
        if o.expires_at is None:
            raise HTTPException(409, "the offer has not been sent")
        return speak(request, message(engine.context().refs, o.hospitals, o.start, o.end, o.expires_at))

    @api.get("/alerts/{item_id:path}/audio")
    def alert_audio(item_id: str, request: Request, who: Principal = need("ops.view")):
        item = gap_item(request, item_id)
        refs = engine_of(request).context().refs
        sites = item.where.get("hospital_ids") or [item.where.get("hospital_id")]
        names = ", ".join(refs.hospitals[h].name for h in sites if h)
        # Typed fields only: severity, hospital names and a fixed reason. No consult or patient detail [00-Boundaries].
        return speak(request, f"Sevaro {item.severity.lower()} alert. {names}. {ALERT_REASONS.get(item.id.split(':')[0], 'needs attention')}.")

    def speak(request, text):
        audio = request.app.state.speech.audio(text)
        if audio is None:
            return JSONResponse({"error": {"status": 503, "code": "speech_unavailable", "message": "text-to-speech unavailable"}, "text": text}, 503)
        return Response(audio, media_type="audio/mpeg")

    @api.get("/audit")
    def audit(request: Request, gap_id: str | None = None, who: Principal = need("ops.view")):
        return jsonable(engine_of(request).desk.audit(gap_id))

    # ---- admin -------------------------------------------------------------------------------------------
    @api.post("/admin/reset")
    def reset(request: Request, who: Principal = need("admin.inject")):
        app = request.app
        app.state.coordinator.reset()
        app.state.engine.desk.reset(who.display_name, app.state.coordinator.clock.now())
        app.state.engine.interventions.reset()
        return {"reset": True, "revision": app.state.coordinator.published.revision}

    @api.post("/admin/clock")
    def set_clock(body: ClockRequest, request: Request, who: Principal = need("admin.inject")):
        if body.mode not in {"fixed", "anchored"}:
            raise HTTPException(422, "mode must be fixed or anchored")
        clock = FixedClock(body.at) if body.mode == "fixed" else AnchoredClock(body.at)
        request.app.state.coordinator.set_clock(clock)
        request.app.state.clock = clock
        return {"mode": clock.mode, "now": request.app.state.coordinator.current_publication().as_of.isoformat()}

    @api.post("/admin/physician-tokens")
    def physician_token(request: Request, physician_id: str = Body(..., embed=True), hours: float = Body(12, embed=True),
                        who: Principal = need("admin.inject")):
        refs = request.app.state.coordinator.refs
        if refs is None or physician_id not in refs.physicians:
            raise HTTPException(404, "unknown physician")
        expires = WALL.now() + timedelta(hours=hours)
        try:
            token = request.app.state.auth.physician_token(physician_id, expires)
        except ValueError as exc:
            raise HTTPException(503, str(exc))
        return {"physician_id": physician_id, "token": token, "expires_at": expires.isoformat()}

    return api

app = create_app()
