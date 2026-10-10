from dataclasses import dataclass
from datetime import datetime
import os


DEFAULT_LATE_LAG_S = 60
DEFAULT_ORPHAN_HOLD_S = 300
DEFAULT_COOLDOWN_S = 120


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("CC_DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/postgres")
    clock_mode: str = os.getenv("CC_CLOCK_MODE", "auto")
    clock_fixed: str | None = os.getenv("CC_CLOCK_FIXED")
    late_lag_s: int = int(os.getenv("CC_LATE_LAG_S", str(DEFAULT_LATE_LAG_S)))
    orphan_hold_s: int = int(os.getenv("CC_ORPHAN_HOLD_S", str(DEFAULT_ORPHAN_HOLD_S)))
    max_batch_rows: int = int(os.getenv("CC_MAX_BATCH_ROWS", "10000"))
    users: str = os.getenv("CC_USERS", "")
    auth_secret: str = os.getenv("CC_AUTH_SECRET", "")
    auth_config: str | None = os.getenv("CC_AUTH_CONFIG")
    auth_off: bool = os.getenv("CC_AUTH", "") == "off"

    def fixed_datetime(self):
        return datetime.fromisoformat(self.clock_fixed) if self.clock_fixed else None


settings = Settings()
