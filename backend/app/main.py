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
from typing import Literal
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from app.act.interventions import InterventionLog
from app.act.offers import OfferDesk, OfferError, message
from app.auth import Accounts, Auth, Principal
from app.clock import AnchoredClock, FixedClock, ServerReceiptClock, make_clock, utc
from app.config import settings
from app.coordinator import MutationCoordinator
from app.db import EventDatabase
from app.ingest.adapters import FIXTURE_VERSION
from app.models import EventInput
from app.service import Engine, base_history, jsonable, load_references, references_from_files
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
    mode: Literal["fixed", "anchored"] | None = None  # fixed, or anchored = runs forward in real time; default keeps the current kind
    at: datetime | None = None  # default: the current simulated time
    advance_s: float | None = None  # jump forward (the web's "+5 min")
    paused: bool | None = None  # True = fixed at the current time, False = resume running


class ReferencesRequest(BaseModel):
    files: dict[str, str]  # the six reference CSVs: file name -> text (REFERENCE_FILES)
    service_date: date | None = None  # only the sample layout needs it: its shift times have no date
    name: str = Field("uploaded references", max_length=200)


MAX_REFERENCE_CHARS = 5_000_000


class Login(BaseModel):
    email: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=1024)
    # Older clients may still select a portal; new clients follow the account's role.
    portal: Literal["operations", "physician"] | None = None


def auth_from_settings() -> Auth:
    """Accounts from CC_USERS (or the local CC_AUTH_CONFIG file) plus the fixed role tokens. Neither: refuse to start."""
    accounts = None
    if settings.users:
        accounts = Accounts(settings.users, settings.auth_secret)
    elif settings.auth_config:
        config = json.loads(Path(settings.auth_config).read_text())
        accounts = Accounts(json.dumps(config["users"]), config["secret"])
    auth = Auth(accounts, settings.coordinator_token, settings.lead_token, settings.admin_token, settings.lead_name, settings.token_secret)
    if not auth.configured:
        raise RuntimeError("No sign-in configured. Run make backend from the repository root for local setup, "
                           "or set CC_USERS and CC_AUTH_SECRET (or the CC_*_TOKEN variables).")
    return auth


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
            refs, ops, dataset = (*references, dataset_of(None)) if references else startup_references(db)
            coordinator = MutationCoordinator(db, clock, settings.late_lag_s, refs=refs, orphan_hold_s=settings.orphan_hold_s)
            engine = Engine(coordinator, ops, None, InterventionLog(url), dataset)
            conns.append(engine.interventions.conn)
            engine.desk = OfferDesk(url, engine.context, base_history(history_path or settings.offer_history, clock.now()))
            api.state.db, api.state.clock, api.state.coordinator, api.state.engine = db, clock, coordinator, engine
            api.state.auth = auth or auth_from_settings()
            api.state.speech = speech or Speech(url)
            engine.speech_available = api.state.speech.available
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

    def dataset_of(directory):
        if not directory or not Path(directory).is_dir():
            return {"name": "unnamed dataset", "description": "", "reference_files": 0}
        folder = Path(directory).resolve()
        name = folder.parent.name if folder.name == "inputs" else folder.name
        return {"name": name, "description": f"reference files from {folder.name}", "reference_files": len(list(folder.glob("*.csv")))}

    def uploaded_dataset(source):
        return {"name": source["name"], "description": "uploaded reference files", "reference_files": len(source["files"])}

    def startup_references(db):
        """Uploaded references (POST /admin/references, kept in the database) win: they are the latest admin action
        and the only source on a host without the CSVs. Otherwise CC_DATA_DIR; otherwise none."""
        source = (db.metadata("references") or {}).get("source")
        directory = settings.reference_dir
        if source:
            if directory:
                log.warning("using the uploaded references %r from the database; CC_DATA_DIR=%r is ignored", source["name"], directory)
            day = date.fromisoformat(source["service_date"]) if source.get("service_date") else None
            return *references_from_files(source["files"], day), uploaded_dataset(source)
        if not directory or not (Path(directory) / "hospitals.csv").exists():
            # Loud, not fatal: /ready reports detection unavailable and decision routes answer 503.
            log.warning("no reference files at CC_DATA_DIR=%r; decisions are unavailable until they are uploaded", directory)
            return None, None, dataset_of(None)
        day = date.fromisoformat(settings.service_date) if settings.service_date else None
        return *load_references(directory, day), dataset_of(directory)

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
        # `detail` like every FastAPI error, so clients show one field; `error.code` for programs.
        return JSONResponse({"detail": exc.message, **exc.payload()}, status_code=exc.status)

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

    @api.post("/auth/login")
    def login(body: Login, request: Request, response: Response):
        accounts = request.app.state.auth.accounts
        if accounts is None:
            raise HTTPException(503, "Account sign-in is not configured on this server (set CC_USERS).")
        token, user, expires = accounts.login(body.email, body.password, body.portal)
        response.headers["Cache-Control"] = "no-store"
        return {"token": token, "expires_at": expires, "user": user.public()}

    @api.get("/auth/me")
    def auth_me(response: Response, who: Principal = need("ops.view", "offers.view_own", "admin.inject")):
        response.headers["Cache-Control"] = "no-store"
        return {"user": who.public()}

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
    async def ingest_csv(request: Request, advance_clock: bool = False, who: Principal = need("admin.inject")):
        """The judges' file: same columns as event_stream.csv, appended without restart [H ch4].
        Events after the clock stay pending (`pending_future`) until it reaches them; `advance_clock=true` moves the
        simulated clock forward to the file's latest event so everything in it is visible at once (never backwards)."""
        text = (await request.body()).decode("utf-8-sig")
        rows = list(csv.DictReader(io.StringIO(text)))
        if len(rows) > settings.max_batch_rows: raise HTTPException(413, "batch exceeds configured row limit")
        report = await run_in_threadpool(request.app.state.coordinator.ingest_raw, rows, FIXTURE_VERSION)
        times = []
        for row in rows:
            try:
                times.append(utc(datetime.fromisoformat(row["event_time"])))
            except (KeyError, TypeError, ValueError):
                continue  # already quarantined by ingest
        latest = max(times, default=None)
        report["latest_event_time"] = latest.isoformat() if latest else None
        clock = request.app.state.clock
        if advance_clock and latest and latest > clock.now():
            moved = FixedClock(latest) if clock.mode == "fixed" else AnchoredClock(latest)
            request.app.state.coordinator.set_clock(moved)
            request.app.state.clock = moved
            report["clock_advanced_to"] = latest.isoformat()
            report["pending_future"] = 0
        return report

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
        view = engine_of(request).candidates_view(gap_id)
        if view is None:
            raise HTTPException(404, "no such gap in the current forecast or queue")
        return view

    @api.get("/gaps/{gap_id:path}/trap-check")
    def trap(gap_id: str, request: Request, who: Principal = need("ops.view")):
        view = engine_of(request).trap_view(gap_id)
        if view is None:
            raise HTTPException(404, "no such gap in the current forecast or queue")
        return view

    @api.post("/interventions")
    def intervene(body: InterventionRequest, request: Request, who: Principal = need("ops.intervene")):
        engine = engine_of(request)
        item = gap_item(request, body.item_id)
        _, d = engine.decisions()
        return jsonable(engine.interventions.record(item, body.kind, body.physician_id, d.views, who.display_name, engine.context().now))

    @api.get("/interventions")
    def interventions(request: Request, state: str | None = None, who: Principal = need("ops.view")):
        rows = engine_of(request).interventions.pending() if state == "pending" else list(engine_of(request).interventions.latest().values())
        return {"items": [{"intervention_id": r["id"], "kind": r["kind"], "item_id": r["item_id"], "reason": r["reason"] or "",
                           "created_at": r["created_at"].isoformat(), "state": r["state"]} for r in rows]}

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
        return shown(engine, engine.desk.propose(body.gap_id, body.physician_id, utc(body.start), utc(body.end),
                                                 body.hospitals or candidate_hospitals, who.display_name, idempotency_key))

    def shown(engine, payload):
        """Offer commands answer with the offer as the screens render it."""
        return engine.offer_view(engine.desk.offer(payload["id"]))

    @api.post("/offers/{offer_id}/approve")
    def approve(offer_id: str, request: Request, who: Principal = need("approvals.decide"), idempotency_key: str | None = Header(None)):
        engine = engine_of(request)
        return shown(engine, engine.desk.approve(offer_id, who.display_name, idempotency_key))

    @api.post("/offers/{offer_id}/reject")
    def reject(offer_id: str, request: Request, reason: str = Body(..., embed=True), who: Principal = need("approvals.decide"),
               idempotency_key: str | None = Header(None)):
        engine = engine_of(request)
        return shown(engine, engine.desk.reject(offer_id, who.display_name, reason, idempotency_key))

    @api.get("/offers")
    def offers(request: Request, who: Principal = need("offers.view_all", "offers.view_own")):
        engine = engine_of(request)
        return {"items": [engine.offer_view(o) for o in engine.desk.offers(who.physician_id)]}  # a physician sees only their own

    @api.get("/offers/{offer_id}")
    def offer(offer_id: str, request: Request, who: Principal = need("offers.view_all", "offers.view_own")):
        engine = engine_of(request)
        return engine.offer_view(engine.desk.offer(offer_id, who.physician_id))

    @api.post("/offers/{offer_id}/accept")
    def accept(offer_id: str, request: Request, who: Principal = need("offers.respond"), idempotency_key: str | None = Header(None)):
        engine = engine_of(request)
        return shown(engine, engine.desk.accept(offer_id, who.physician_id, idempotency_key))

    @api.post("/offers/{offer_id}/decline")
    def decline(offer_id: str, request: Request, who: Principal = need("offers.respond"), idempotency_key: str | None = Header(None)):
        engine = engine_of(request)
        return shown(engine, engine.desk.decline(offer_id, who.physician_id, idempotency_key))

    @api.get("/me/offers")
    def my_offers(request: Request, who: Principal = need("offers.view_own")):
        """The physician screen: their own offers once a lead has sent them (never proposals or rejections)."""
        engine = engine_of(request)
        return {"now": engine.context().now.isoformat(),
                "items": [engine.offer_view(o) for o in engine.desk.offers(who.physician_id) if o.sent_at is not None]}

    @api.post("/me/offers/{offer_id}/{choice}")
    def my_reply(offer_id: str, choice: Literal["accept", "decline"], request: Request, who: Principal = need("offers.respond"),
                 idempotency_key: str | None = Header(None)):
        engine = engine_of(request)
        reply = engine.desk.accept if choice == "accept" else engine.desk.decline
        return shown(engine, reply(offer_id, who.physician_id, idempotency_key))

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
        return engine_of(request).audit_view(gap_id)

    # ---- admin -------------------------------------------------------------------------------------------
    @api.post("/admin/references")
    def upload_references(body: ReferencesRequest, request: Request, who: Principal = need("admin.inject")):
        """Load or replace the reference CSVs without a redeploy (a host has no CC_DATA_DIR). Checked by the same loaders,
        then stored in the database with the switch, so restarts keep them. Loaded events stay: POST /admin/reset to
        start the new dataset with an empty stream."""
        if sum(map(len, body.files.values())) > MAX_REFERENCE_CHARS:
            raise HTTPException(413, "reference files exceed the size limit")
        try:
            refs, ops = references_from_files(body.files, body.service_date)
        except (ValueError, KeyError, csv.Error) as exc:  # KeyError includes an unknown time zone
            raise HTTPException(422, f"reference files rejected: {exc}") from None
        source = {"name": body.name, "service_date": body.service_date.isoformat() if body.service_date else None, "files": body.files}
        report = request.app.state.engine.use_references(refs, ops, source, uploaded_dataset(source))
        return {"activated": True, "dataset": request.app.state.engine.dataset, "revision": report["revision"],
                "hospitals": len(refs.hospitals), "physicians": len(refs.physicians)}

    @api.post("/admin/reset")
    def reset(request: Request, who: Principal = need("admin.inject")):
        app = request.app
        app.state.coordinator.reset()
        app.state.engine.desk.reset(who.display_name, app.state.coordinator.clock.now())
        app.state.engine.interventions.reset()
        return {"reset": True, "revision": app.state.coordinator.published.revision}

    @api.post("/admin/clock")
    def set_clock(body: ClockRequest, request: Request, who: Principal = need("admin.inject")):
        """Set, pause, resume or jump the simulated clock. Offers refuse commands from a clock moved behind them."""
        current = request.app.state.clock
        at = body.at or current.now()
        if body.advance_s:
            at += timedelta(seconds=body.advance_s)
        mode = "fixed" if body.paused else "anchored" if body.paused is False else body.mode or ("fixed" if current.mode == "fixed" else "anchored")
        clock = FixedClock(at) if mode == "fixed" else AnchoredClock(at)
        request.app.state.coordinator.set_clock(clock)
        request.app.state.clock = clock
        return {"mode": clock.mode, "now": request.app.state.coordinator.current_publication().as_of.isoformat(), "paused": clock.mode == "fixed"}

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
