"""Tokens and role permissions [00-Boundaries: Roles, authentication and RBAC]. Standard library only.

Coordinator, lead and admin use fixed tokens from the environment; a physician token is an HMAC over the
physician ID and an expiry. Fail closed: a role whose token is not configured cannot sign in.
"""
import base64
import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timezone

PERMISSIONS = {
    "coordinator": ("ops.view", "ops.intervene", "offers.view_all"),
    "lead": ("ops.view", "approvals.decide", "offers.view_all"),
    "physician": ("offers.view_own", "offers.respond"),
    "admin": ("admin.inject",),
}


@dataclass(frozen=True)
class Principal:
    role: str
    display_name: str
    physician_id: str | None = None

    @property
    def permissions(self) -> tuple[str, ...]:
        return PERMISSIONS[self.role]

    def payload(self):
        return {"role": self.role, "display_name": self.display_name, "physician_id": self.physician_id, "permissions": list(self.permissions)}


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


@dataclass(frozen=True)
class Auth:
    coordinator_token: str | None = None
    lead_token: str | None = None
    admin_token: str | None = None
    lead_name: str = "Clinical lead"
    secret: str | None = None  # signs physician tokens; unset = no physician sign-in

    def physician_token(self, physician_id: str, expires: datetime) -> str:
        if not self.secret:
            raise ValueError("physician tokens need CC_TOKEN_SECRET")
        body = f"{physician_id}.{int(expires.timestamp())}"
        return f"phy.{_b64(body.encode())}.{_b64(hmac.new(self.secret.encode(), body.encode(), hashlib.sha256).digest())}"

    def identify(self, token: str | None, now: datetime) -> Principal | None:
        """None for a missing, wrong or expired token (the API answers 401)."""
        if not token:
            return None
        for role, expected, name in (("coordinator", self.coordinator_token, "Coordinator"), ("lead", self.lead_token, self.lead_name),
                                     ("admin", self.admin_token, "Admin")):
            if expected and hmac.compare_digest(token.encode(), expected.encode()):
                return Principal(role, name)
        if not (self.secret and token.startswith("phy.") and token.count(".") == 2):
            return None
        _, body64, sig64 = token.split(".")
        try:
            body = base64.urlsafe_b64decode(body64 + "=" * (-len(body64) % 4)).decode()
            physician_id, expiry = body.rsplit(".", 1)
            expires = datetime.fromtimestamp(int(expiry), timezone.utc)
        except ValueError:
            return None
        good = _b64(hmac.new(self.secret.encode(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig64.encode(), good.encode()) or now >= expires:
            return None
        return Principal("physician", physician_id, physician_id)
