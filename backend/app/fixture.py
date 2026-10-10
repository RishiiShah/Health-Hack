"""Strict read-only test helper; ingestion uses coordinator.ingest_raw for quarantine."""
import csv
from pathlib import Path
from app.ingest.adapters import FIXTURE_VERSION
from app.ingest.pipeline import normalize_row
from app.models import EventInput


def load_fixture(path: str | Path) -> list[EventInput]:
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        return [normalize_row(raw, FIXTURE_VERSION) for raw in csv.DictReader(handle)]
