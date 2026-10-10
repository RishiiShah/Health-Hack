from contextlib import asynccontextmanager
import json
from uuid import uuid4
from typing import Literal
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, Field
from app.auth import Auth, User, require
from app.config import settings
from app.clock import make_clock
from app.db import EventDatabase
from app.coordinator import MutationCoordinator
from app.models import EventInput

OPERATIONS = ("coordinator", "lead")


class Login(BaseModel):
    email: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=1024)
    # Older clients may still select a portal; new clients follow the account's role.
    portal: Literal["operations", "physician"] | None = None


def auth_from_settings() -> Auth | None:
    if settings.auth_off:
        return None
    if settings.users:
        return Auth(settings.users, settings.auth_secret)
    if settings.auth_config:
        config = json.loads(Path(settings.auth_config).read_text())
        return Auth(json.dumps(config["users"]), config["secret"])
    raise RuntimeError("Run make backend from the repository root for local setup, or set CC_USERS and CC_AUTH_SECRET.")


_SETTINGS = object()

def create_app(database_url: str | None = None, test_clock=None, auth: Auth | None | object = _SETTINGS) -> FastAPI:
    epoch = str(uuid4())
    # Readers within the same second share one encoding. Any commit or newly visible event
    # (a new state object) re-encodes at once; only clock-derived fields may lag by <1 s.
    snapshot_cache = [(None, None, None, b"")]

    @asynccontextmanager
    async def lifespan(api: FastAPI):
        db = EventDatabase(database_url or settings.database_url)
        try:
            events = db.events()
            clock = test_clock or make_clock(settings.clock_mode, settings.fixed_datetime(), max((e.event_time for e in events), default=None))
            api.state.db = db
            api.state.clock = clock
            api.state.coordinator = MutationCoordinator(db, clock, settings.late_lag_s, orphan_hold_s=settings.orphan_hold_s)
            yield
        finally:
            db.conn.close()

    api = FastAPI(title="Sevaro Command Center API", version="0.1.0", lifespan=lifespan)
    api.state.auth = auth_from_settings() if auth is _SETTINGS else auth

    @api.post("/auth/login")
    def login(body: Login, request: Request, response: Response):
        if request.app.state.auth is None: raise HTTPException(503, "Sign-in is turned off on this server (CC_AUTH=off).")
        token, user, expires = request.app.state.auth.login(body.email, body.password, body.portal)
        response.headers["Cache-Control"] = "no-store"
        return {"token": token, "expires_at": expires, "user": user.public()}

    @api.get("/auth/me")
    def me(response: Response, user: User | None = require("coordinator", "lead", "physician")):
        response.headers["Cache-Control"] = "no-store"
        return {"user": user.public() if user else None}

    @api.get("/health")
    def health(): return {"status":"ok"}

    @api.get("/ready")
    def ready(request: Request):
        p = request.app.state.coordinator.published
        return {"ready":True, "revision":p.revision, "event_count":p.event_count, "clock_mode":request.app.state.clock.mode,
            "capabilities":{"event_ingest":True,"durable_event_log":True,"consult_replay":True,"fixture_adapter":True,
                "orphan_holding":True,"reference_validation":False,"physician_state":False,"detection":False,
                "coverage_forecast":False,"websocket":False,"authentication":request.app.state.auth is not None}}

    @api.post("/events")
    def ingest(request: Request, payload: EventInput | list[EventInput], _: User | None = require(*OPERATIONS)):
        rows = payload if isinstance(payload, list) else [payload]
        if len(rows) > settings.max_batch_rows: raise HTTPException(413, "batch exceeds configured row limit")
        coordinator = request.app.state.coordinator
        report = coordinator.ingest(rows)
        if report["unresolved"]:
            report["capability_warning"] = "Unresolved events remain held until dependencies arrive or the server-time deadline expires."
        return report

    @api.get("/snapshot")
    def snapshot(request: Request, _: User | None = require(*OPERATIONS)):
        coordinator = request.app.state.coordinator
        p = coordinator.current_publication()
        revision, state, second, body = snapshot_cache[0]
        if (revision, second) != (p.revision, p.as_of.replace(microsecond=0)) or state is not p.state:
            body = json.dumps(snapshot_body(p, request.app.state.clock.mode), separators=(",", ":")).encode()
            snapshot_cache[0] = (p.revision, p.state, p.as_of.replace(microsecond=0), body)
        return Response(body, media_type="application/json")

    def snapshot_body(p, clock_mode):
        open_rows = []
        for c in p.state.consults.values():
            if c.stage == "Signed Off": continue
            open_rows.append({"consult_id":c.consult_id, "hospital_id":c.hospital_id, "consult_type":c.consult_type,
                "physician_id":c.owner, "current_stage":c.stage, "stage_entered_at":c.entered_at.isoformat(),
                "minutes_in_stage":max(0, int((p.as_of-c.entered_at).total_seconds()//60)),
                "minutes_since_received":max(0, int((p.as_of-c.received_at).total_seconds()//60))})
        return {"revision":p.revision, "reference_revision":0, "clock_revision":0, "epoch":epoch, "sequence":p.revision,
            "clock":{"mode":clock_mode, "now":p.as_of.isoformat()}, "headline":{"open_consults":len(open_rows)}, "consults":open_rows,
            "physicians":{"supported":False,"items":[]}, "hospitals":{"supported":False,"items":[]},
            "queue":{"supported":False,"items":[]}, "coverage":{"supported":False},
            "capabilities":{"orphan_holding":True,"reference_validation":False,"physician_state":False,"detection":False},
            "data_quality":{"supported":False,"accepted_events":p.event_count}}

    @api.get("/consults/{consult_id}")
    def consult(consult_id: str, request: Request, _: User | None = require(*OPERATIONS)):
        c = request.app.state.coordinator.current_publication().state.consults.get(consult_id)
        if c is None: raise HTTPException(404, "consult not found")
        return {"consult_id":c.consult_id, "stage":c.stage, "owner":c.owner, "history":[{"stage":s,"at":t.isoformat()} for s,t in c.history]}

    return api

app = create_app()
