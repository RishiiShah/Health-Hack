"""Versioned, explicit adapter for the supplied event_stream.csv fixture."""
FIXTURE_VERSION = "sample-csv-v1"
DESCRIPTION = {
    ("consult_received", "Stroke consult request received"): ("Stroke", None),
    ("consult_received", "General Neuro consult request received"): ("General Neuro", None),
    ("incoming_call_ended", "Call ends; phone-only consult (outside treatment window)"): (None, "phone_complete"),
    ("incoming_call_ended", "Call ends"): (None, "continue"),
    ("outgoing_call_ended", "Call ends"): (None, "continue"),
    # Scenario-pack wording for the same events.
    ("incoming_call_ended", "Clinical phone-only consultation completed; note not started"): (None, "phone_complete"),
    ("outgoing_call_ended", "Hospital follow-up call ends"): (None, "continue"),
    ("routing_attempt_failed", "No available credentialed provider; retry scheduled"): (None, "retry_in_5m"),
}
STATUS = {"Self-reported status: Available": "Available", "Self-reported status: In Meeting": "In Meeting", "Self-reported status: Temporarily Unavailable": "Temporarily Unavailable"}


def adapt_fixture(row: dict) -> dict:
    row = dict(row)
    kind, desc = row.get("event_type"), row.get("description", "")
    consult_type, value = DESCRIPTION.get((kind, desc), (None, None))
    if kind == "physician_status_changed": value = STATUS.get(desc)
    if kind == "consult_received" and not consult_type: raise ValueError("unknown receipt description")
    if kind == "routing_attempt_failed" and not value: raise ValueError("unknown routing failure description")
    row["consult_type"] = row.get("consult_type") or consult_type
    row["value"] = row.get("value") or value
    row["source"] = "base"
    row["adapter_version"] = FIXTURE_VERSION
    return row
