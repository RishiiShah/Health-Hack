from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path


DEFAULT_LATE_LAG_S = 60
DEFAULT_ORPHAN_HOLD_S = 300
DEFAULT_COOLDOWN_S = 120


@dataclass(frozen=True)
class Settings:
    db_path: str = os.getenv("CC_DB_PATH", str(Path(__file__).resolve().parents[1] / "cc.db"))
    clock_mode: str = os.getenv("CC_CLOCK_MODE", "auto")
    clock_fixed: str | None = os.getenv("CC_CLOCK_FIXED")
    late_lag_s: int = int(os.getenv("CC_LATE_LAG_S", str(DEFAULT_LATE_LAG_S)))
    orphan_hold_s: int = int(os.getenv("CC_ORPHAN_HOLD_S", str(DEFAULT_ORPHAN_HOLD_S)))
    max_batch_rows: int = int(os.getenv("CC_MAX_BATCH_ROWS", "10000"))

    def fixed_datetime(self):
        return datetime.fromisoformat(self.clock_fixed) if self.clock_fixed else None


settings = Settings()
