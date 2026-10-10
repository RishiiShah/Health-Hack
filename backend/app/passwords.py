"""Standard-library password hashing shared by sign-in and local account setup."""
import hashlib
import hmac
import secrets

# OWASP's PBKDF2-HMAC-SHA256 recommendation; old stored work factors still verify.
ITERATIONS = 600_000


def hash_password(password: str, salt: str | None = None, iterations: int = ITERATIONS) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), iterations).hex()
    return f"pbkdf2_sha256${iterations}${salt}${digest}"


def valid_password_hash(stored: str) -> bool:
    try:
        algorithm, iterations, salt, digest = stored.split("$")
        return (algorithm == "pbkdf2_sha256" and 1 <= int(iterations) <= 10_000_000
                and len(bytes.fromhex(salt)) >= 16 and len(bytes.fromhex(digest)) == 32)
    except (ValueError, TypeError, AttributeError):
        return False


def check_password(password: str, stored: str) -> bool:
    if not valid_password_hash(stored):
        return False
    _, iterations, salt, _ = stored.split("$")
    return hmac.compare_digest(hash_password(password, salt, int(iterations)), stored)
