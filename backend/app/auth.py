"""Sign-in and role checks: accounts from CC_USERS, PBKDF2 password hashes, HMAC-signed bearer tokens.

Generate a password hash with: python -m app.auth
"""
import base64
from dataclasses import dataclass
import getpass
import hashlib
import hmac
import json
import secrets
import time
from fastapi import Depends, HTTPException, Request
from app.passwords import ITERATIONS, check_password, hash_password, valid_password_hash

ROLES = {"coordinator": "Operations coordinator", "lead": "Clinical lead", "physician": "Physician"}
# Which sign-in page each role uses; the account, not the page, decides the role.
PORTALS = {"operations": ("coordinator", "lead"), "physician": ("physician",)}
TOKEN_TTL_S = 12 * 3600


# Unknown accounts also perform password hashing instead of returning immediately.
_UNKNOWN_ACCOUNT = hash_password(secrets.token_hex(16))


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


@dataclass(frozen=True)
class User:
    email: str
    name: str
    role: str
    physician_id: str | None = None

    def public(self) -> dict:
        return {"email": self.email, "name": self.name, "role": self.role, "role_label": ROLES[self.role], "physician_id": self.physician_id}


class Auth:
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
            if row["role"] not in ROLES:
                raise ValueError(f"unknown role for {email}: {row['role']}")
            if (row["role"] == "physician") != bool(row.get("physician_id")):
                raise ValueError(f"{email}: physician accounts, and only they, need a physician_id")
            if email in self.accounts:
                raise ValueError(f"duplicate account: {email}")
            self.accounts[email] = (User(email, row["name"], row["role"], row.get("physician_id")), row["password_hash"])
        if not self.accounts:
            raise ValueError("CC_USERS has no accounts")

    def login(self, email: str, password: str, portal: str | None = None) -> tuple[str, User, int]:
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

    def verify(self, token: str) -> User | None:
        if len(token) > 4096:
            return None
        body, _, signature = token.partition(".")
        expected = _b64(hmac.new(self.secret, body.encode(), hashlib.sha256).digest())
        if not body or not hmac.compare_digest(signature.encode(), expected.encode()):
            return None
        try:
            claims = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
            if not isinstance(claims, dict) or not isinstance(claims.get("sub"), str) or type(claims.get("exp")) is not int:
                return None
            entry = self.accounts.get(claims["sub"])
            return entry[0] if entry and claims["exp"] > self.now() else None
        except (ValueError, UnicodeError):
            return None


def require(*roles: str):
    """Route dependency: the signed-in user, if their role is allowed. With CC_AUTH=off there is no user."""
    def check(request: Request) -> User | None:
        auth: Auth | None = request.app.state.auth
        if auth is None:
            return None
        scheme, _, token = request.headers.get("authorization", "").partition(" ")
        user = auth.verify(token) if scheme.lower() == "bearer" else None
        if user is None:
            raise HTTPException(401, "Sign in to continue.", headers={"WWW-Authenticate": "Bearer"})
        if user.role not in roles:
            raise HTTPException(403, f"A {ROLES[user.role].lower()} can't do this.")
        return user
    return Depends(check)


if __name__ == "__main__":
    password = getpass.getpass("Password (at least 8 characters): ")
    if len(password) < 8 or len(password) > 1024:
        raise SystemExit("Use a password between 8 and 1024 characters.")
    if password != getpass.getpass("Again: "):
        raise SystemExit("Passwords don't match")
    print(hash_password(password))
