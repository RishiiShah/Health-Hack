"""Sign-in and role permissions. Standard library only.

Three kinds of bearer token, one permission table:
- account sign-in (web and mobile): `POST /auth/login` with an email and password from CC_USERS (PBKDF2 hashes),
  answered with an HMAC-signed token that expires after 12 hours;
- physician links: an HMAC over the physician ID and an expiry, issued by `POST /admin/physician-tokens`;
- fixed tokens per role from the environment, for scripts and the live injector.
Fail closed: a missing, wrong or expired token is 401, and the server checks the permission on every request.

Generate a password hash with: python -m app.auth
"""
import base64
import getpass
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from fastapi import HTTPException
from app.passwords import check_password, hash_password, valid_password_hash

ROLES = {"coordinator": "Operations coordinator", "lead": "Clinical lead", "physician": "Physician", "admin": "Admin"}
# Coordinator and lead also run the live injector (the web Data page is in both workspaces).
PERMISSIONS = {
    "coordinator": ("ops.view", "ops.intervene", "offers.view_all", "admin.inject"),
    "lead": ("ops.view", "approvals.decide", "offers.view_all", "admin.inject"),
    "physician": ("offers.view_own", "offers.respond"),
    "admin": ("admin.inject",),
}
# Which sign-in page each role uses; the account, not the page, decides the role.
PORTALS = {"operations": ("coordinator", "lead"), "physician": ("physician",)}
TOKEN_TTL_S = 12 * 3600
# Unknown accounts also perform password hashing instead of returning immediately.
_UNKNOWN_ACCOUNT = hash_password(secrets.token_hex(16))


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


@dataclass(frozen=True)
class Principal:
    role: str
    display_name: str
    physician_id: str | None = None
    email: str | None = None

    @property
    def permissions(self) -> tuple[str, ...]:
        return PERMISSIONS[self.role]

    def payload(self):
        """`GET /me` (contract shape)."""
        return {"role": self.role, "display_name": self.display_name, "physician_id": self.physician_id, "permissions": list(self.permissions)}

    def public(self):
        """`/auth/login` and `/auth/me` (web and mobile shape)."""
        return {"email": self.email, "name": self.display_name, "role": self.role, "role_label": ROLES[self.role], "physician_id": self.physician_id}


class Accounts:
    """Email and password accounts from CC_USERS: [{email, name, role, physician_id?, password_hash}]."""

    def __init__(self, users_json: str, secret: str, now=time.time):
        if len(secret) < 32:
            raise ValueError("CC_AUTH_SECRET must be at least 32 characters")
        self.secret, self.now, self.accounts = secret.encode(), now, {}
        rows = json.loads(users_json)
        if not isinstance(rows, list):
            raise ValueError("CC_USERS must be a JSON list of accounts")
        for row in rows:
            email = row["email"].strip().lower()
            if not email or not row["name"].strip():
                raise ValueError("Account email and name must not be blank")
            if not valid_password_hash(row.get("password_hash")):
                raise ValueError(f"Invalid password hash for {email}; regenerate it with python -m app.auth")
            if row["role"] not in PORTALS["operations"] + PORTALS["physician"]:
                raise ValueError(f"unknown role for {email}: {row['role']}")
            if (row["role"] == "physician") != bool(row.get("physician_id")):
                raise ValueError(f"{email}: physician accounts, and only they, need a physician_id")
            if email in self.accounts:
                raise ValueError(f"duplicate account: {email}")
            self.accounts[email] = (Principal(row["role"], row["name"], row.get("physician_id"), email), row["password_hash"])
        if not self.accounts:
            raise ValueError("CC_USERS has no accounts")

    def login(self, email: str, password: str, portal: str | None = None) -> tuple[str, Principal, int]:
        entry = self.accounts.get(email.strip().lower())
        if not check_password(password, entry[1] if entry else _UNKNOWN_ACCOUNT) or entry is None:
            raise HTTPException(401, "Email or password is incorrect.")
        user = entry[0]
        if portal is not None and user.role not in PORTALS.get(portal, ()):
            right = next(p for p, roles in PORTALS.items() if user.role in roles).capitalize()
            raise HTTPException(403, f"This is a {ROLES[user.role].lower()} account. Sign in as {right} instead.")
        expires = int(self.now()) + TOKEN_TTL_S
        body = _b64(json.dumps({"sub": user.email, "exp": expires, "sid": secrets.token_urlsafe(16)}).encode())
        return f"{body}.{_b64(hmac.new(self.secret, body.encode(), hashlib.sha256).digest())}", user, expires

    def verify(self, token: str) -> Principal | None:
        if len(token) > 4096:
            return None
        body, _, signature = token.partition(".")
        expected = _b64(hmac.new(self.secret, body.encode(), hashlib.sha256).digest())
        if not body or not hmac.compare_digest(signature.encode(), expected.encode()):
            return None
        try:
            claims = json.loads(_unb64(body))
            if not isinstance(claims, dict) or not isinstance(claims.get("sub"), str) or type(claims.get("exp")) is not int:
                return None
            entry = self.accounts.get(claims["sub"])
            return entry[0] if entry and claims["exp"] > self.now() else None
        except (ValueError, UnicodeError):
            return None


@dataclass(frozen=True)
class Auth:
    accounts: Accounts | None = None
    coordinator_token: str | None = None
    lead_token: str | None = None
    admin_token: str | None = None
    lead_name: str = "Clinical lead"
    secret: str | None = None  # signs physician links; unset = no physician links

    @property
    def configured(self) -> bool:
        return bool(self.accounts or self.coordinator_token or self.lead_token or self.admin_token)

    def physician_token(self, physician_id: str, expires: datetime) -> str:
        if not self.secret:
            raise ValueError("physician tokens need CC_TOKEN_SECRET")
        body = f"{physician_id}.{int(expires.timestamp())}"
        return f"phy.{_b64(body.encode())}.{_b64(hmac.new(self.secret.encode(), body.encode(), hashlib.sha256).digest())}"

    def identify(self, token: str | None, now: datetime) -> Principal | None:
        """None for a missing, wrong or expired token (the API answers 401). `now` is wall time, never the simulation clock."""
        if not token:
            return None
        for role, expected, name in (("coordinator", self.coordinator_token, "Coordinator"), ("lead", self.lead_token, self.lead_name),
                                     ("admin", self.admin_token, "Admin")):
            if expected and hmac.compare_digest(token.encode(), expected.encode()):
                return Principal(role, name)
        if token.startswith("phy.") and token.count(".") == 2:
            return self._physician(token, now)
        return self.accounts.verify(token) if self.accounts else None

    def _physician(self, token, now):
        if not self.secret:
            return None
        _, body64, sig64 = token.split(".")
        try:
            body = _unb64(body64).decode()
            physician_id, expiry = body.rsplit(".", 1)
            expires = datetime.fromtimestamp(int(expiry), timezone.utc)
        except (ValueError, UnicodeError):
            return None
        good = _b64(hmac.new(self.secret.encode(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig64.encode(), good.encode()) or now >= expires:
            return None
        return Principal("physician", physician_id, physician_id)


if __name__ == "__main__":
    password = getpass.getpass("Password (at least 8 characters): ")
    if len(password) < 8 or len(password) > 1024:
        raise SystemExit("Use a password between 8 and 1024 characters.")
    if password != getpass.getpass("Again: "):
        raise SystemExit("Passwords don't match")
    print(hash_password(password))
