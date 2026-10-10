from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    db_path: str = os.getenv("CC_DB_PATH", str(Path(__file__).resolve().parents[1] / "cc.db"))
    data_dir: str = os.getenv("CC_DATA_DIR", str(Path(__file__).resolve().parents[2] / "data"))
    clock_mode: str = os.getenv("CC_CLOCK_MODE", "auto")
    clock_fixed: str | None = os.getenv("CC_CLOCK_FIXED")
    service_date: str = os.getenv("CC_SERVICE_DATE", "2026-03-17")
    late_lag_s: int = int(os.getenv("CC_LATE_LAG_S", "60"))
    max_batch_rows: int = int(os.getenv("CC_MAX_BATCH_ROWS", "10000"))
    max_upload_bytes: int = int(os.getenv("CC_MAX_UPLOAD_BYTES", "10000000"))

    def fixed_datetime(self):
        return datetime.fromisoformat(self.clock_fixed) if self.clock_fixed else None


settings = Settings()
