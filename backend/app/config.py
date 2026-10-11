from dataclasses import dataclass
from datetime import datetime
import os


DEFAULT_LATE_LAG_S = 60
DEFAULT_ORPHAN_HOLD_S = 300
DEFAULT_COOLDOWN_S = 120
DEFAULT_FORECAST_CLIFF_LOOKAHEAD_MIN = 120
OFFICIAL_REFERENCE_FINGERPRINT = "81602969911fe81fc1d5db5a51595fb5124d07ac5f5e97623a21e1232701d72d"


@dataclass(frozen=True)
class OverloadPolicy:
    open_warning: int = 3
    open_critical: int = 4
    rate_multiple: float = 1.5
    window_minutes: int = 120
    minimum_peers: int = 3

    def __post_init__(self):
        if not (0 < self.open_warning < self.open_critical and self.rate_multiple > 0
                and self.window_minutes > 0 and self.minimum_peers > 0):
            raise ValueError("invalid overload policy")


DEFAULT_OVERLOAD = OverloadPolicy()


@dataclass(frozen=True)
class Settings:
    # Runtime references are the supplied Sevaro kit. Only in-process synthetic tests override this field.
    reference_fingerprint: str | None = OFFICIAL_REFERENCE_FINGERPRINT
    database_url: str = os.getenv("CC_DATABASE_URL", "")  # the production RDS database, locally too (root .env)
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
    web_dir: str | None = os.getenv("CC_WEB_DIR")  # built web app (web/dist), served on the API's origin

    def fixed_datetime(self):
        return datetime.fromisoformat(self.clock_fixed) if self.clock_fixed else None


settings = Settings()
