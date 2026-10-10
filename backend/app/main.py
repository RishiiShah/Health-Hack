from contextlib import asynccontextmanager
from uuid import uuid4
from fastapi import FastAPI, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from app.config import settings
from app.clock import make_clock
from app.db import EventDatabase
from app.coordinator import MutationCoordinator
from app.models import EventInput

def create_app(db_path: str | None = None, test_clock=None) -> FastAPI:
    epoch = str(uuid4())

    @asynccontextmanager
    async def lifespan(api: FastAPI):
        db = EventDatabase(db_path or settings.db_path)
        events = db.events()
        clock = test_clock or make_clock(settings.clock_mode, settings.fixed_datetime(), max((e.event_time for e in events), default=None))
        api.state.db = db
        api.state.clock = clock
        api.state.coordinator = MutationCoordinator(db, clock, settings.late_lag_s)
        try:
            yield
        finally:
            db.conn.close()

    api = FastAPI(title="Sevaro Command Center API", version="0.1.0", lifespan=lifespan)

    @api.get("/health")
    def health(): return {"status":"ok"}

    @api.get("/ready")
    def ready(request: Request):
        p = request.app.state.coordinator.published
        return {"ready":True, "revision":p.revision, "event_count":p.event_count, "clock_mode":request.app.state.clock.mode,
            "capabilities":{"event_ingest":True,"durable_event_log":True,"consult_replay":True,"fixture_adapter":True,
                "orphan_holding":False,"reference_validation":False,"physician_state":False,"detection":False,
                "coverage_forecast":False,"websocket":False,"authentication":False}}

    @api.post("/events")
    async def ingest(request: Request, payload: EventInput | list[EventInput]):
        rows = payload if isinstance(payload, list) else [payload]
        if len(rows) > settings.max_batch_rows: raise HTTPException(413, "batch exceeds configured row limit")
        coordinator = request.app.state.coordinator
        report = await run_in_threadpool(coordinator.ingest, rows)
        if report["unresolved"]:
            report["capability_warning"] = "Unresolved consult events were quarantined because G4 orphan holding is not implemented."
        return report

    @api.get("/snapshot")
    def snapshot(request: Request):
        coordinator = request.app.state.coordinator
        p = coordinator.current_publication()
        open_rows = []
        for c in p.state.consults.values():
            if c.stage == "Signed Off": continue
            open_rows.append({"consult_id":c.consult_id, "hospital_id":c.hospital_id, "consult_type":c.consult_type,
                "physician_id":c.owner, "current_stage":c.stage, "stage_entered_at":c.entered_at.isoformat(),
                "minutes_in_stage":max(0, int((p.as_of-c.entered_at).total_seconds()//60)),
                "minutes_since_received":max(0, int((p.as_of-c.received_at).total_seconds()//60))})
        return {"revision":p.revision, "reference_revision":0, "clock_revision":0, "epoch":epoch, "sequence":p.revision,
            "clock":{"mode":request.app.state.clock.mode, "now":p.as_of.isoformat()}, "headline":{"open_consults":len(open_rows)}, "consults":open_rows,
            "physicians":{"supported":False,"items":[]}, "hospitals":{"supported":False,"items":[]},
            "queue":{"supported":False,"items":[]}, "coverage":{"supported":False},
            "capabilities":{"orphan_holding":False,"reference_validation":False,"physician_state":False,"detection":False},
            "data_quality":{"supported":False,"accepted_events":p.event_count}}

    @api.get("/consults/{consult_id}")
    def consult(consult_id: str, request: Request):
        c = request.app.state.coordinator.current_publication().state.consults.get(consult_id)
        if c is None: raise HTTPException(404, "consult not found")
        return {"consult_id":c.consult_id, "stage":c.stage, "owner":c.owner, "history":[{"stage":s,"at":t.isoformat()} for s,t in c.history]}

    return api

app = create_app()
