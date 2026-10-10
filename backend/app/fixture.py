"""Read-only loader for the supplied CSV. Source files are never modified."""
import csv
from datetime import datetime
from pathlib import Path
from app.ingest.adapters import adapt_fixture
from app.models import EventInput

def load_fixture(path: str | Path) -> list[EventInput]:
    result = []
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        for raw in csv.DictReader(handle):
            adapted = adapt_fixture(raw)
            result.append(EventInput(event_id=adapted["event_id"], event_time=datetime.fromisoformat(adapted["event_time"]),
                ingested_at=datetime.fromisoformat(adapted["ingested_at"]), consult_id=adapted.get("consult_id") or None,
                event_type=adapted["event_type"], physician_id=adapted.get("physician_id") or None,
                hospital_id=adapted.get("hospital_id") or None, consult_type=adapted.get("consult_type"), value=adapted.get("value"),
                source=adapted["source"], adapter_version=adapted["adapter_version"], raw_json=raw))
    return result
