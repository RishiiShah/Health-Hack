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
    reference_dir: str | None = os.getenv("CC_DATA_DIR")  # hospitals, shifts, roster, credentials, baseline, coverage CSVs
    service_date: str | None = os.getenv("CC_SERVICE_DATE")  # only for the sample layout, whose shift times have no date
    offer_history: str | None = os.getenv("CC_OFFER_HISTORY")  # offers sent outside this tool (R7/R8)
    coordinator_token: str | None = os.getenv("CC_COORDINATOR_TOKEN")
    lead_token: str | None = os.getenv("CC_LEAD_TOKEN")
    admin_token: str | None = os.getenv("CC_ADMIN_TOKEN")
    lead_name: str = os.getenv("CC_LEAD_NAME", "Clinical lead")
    token_secret: str | None = os.getenv("CC_TOKEN_SECRET")
    sweep_s: float = float(os.getenv("CC_SWEEP_S", "5"))  # offer expiry and orphan deadlines; 0 = only on requests
    users: str = os.getenv("CC_USERS", "")  # sign-in accounts: JSON list with PBKDF2 hashes (python -m app.auth)
    auth_secret: str = os.getenv("CC_AUTH_SECRET", "")  # 32+ characters; signs account sign-in tokens
    auth_config: str | None = os.getenv("CC_AUTH_CONFIG")  # local file {users, secret} written by scripts/setup_auth.py

    def fixed_datetime(self):
        return datetime.fromisoformat(self.clock_fixed) if self.clock_fixed else None


settings = Settings()
