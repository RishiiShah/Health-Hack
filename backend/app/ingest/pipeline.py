"""G1 entry point for P1's future JSON/CSV upload routes."""
from app.ingest.adapters import adapt_fixture, FIXTURE_VERSION
from app.models import EventInput


def normalize_row(raw: dict, adapter: str = "canonical-v1") -> EventInput:
    if not isinstance(raw, dict): raise ValueError("event row must be an object")
    if adapter == "canonical-v1":
        return EventInput.model_validate(raw)
    if adapter != FIXTURE_VERSION: raise ValueError(f"unsupported adapter: {adapter}")
    required = {"event_id", "event_time", "ingested_at", "event_type", "description"}
    if not required <= raw.keys() or any(not raw[key] for key in required):
        raise ValueError("sample CSV row is missing required fields")
    adapted = adapt_fixture(raw)
    fields = {key: adapted[key] for key in EventInput.model_fields if key in adapted}
    for key in ("consult_id", "physician_id", "hospital_id"):
        fields[key] = fields.get(key) or None
    return EventInput(**{**fields, "raw_json": dict(raw)})
