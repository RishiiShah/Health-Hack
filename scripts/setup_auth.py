"""Create local credentials without a venv, plaintext password file, or shell exports."""
import argparse
import getpass
import json
import os
from pathlib import Path
import secrets
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.passwords import hash_password, valid_password_hash

CONFIG = Path(os.environ.get("CC_LOCAL_AUTH_FILE", str(ROOT / "backend" / ".local" / "auth.json"))).resolve()


def read_config(path: Path) -> dict:
    config = json.loads(path.read_text())
    if (not isinstance(config, dict) or not isinstance(config.get("secret"), str)
            or len(config["secret"]) < 32 or not isinstance(config.get("users"), list) or not config["users"]):
        raise ValueError("Invalid local auth config; expected a signing secret and accounts")
    for user in config["users"]:
        if not isinstance(user, dict) or not valid_password_hash(user.get("password_hash")):
            raise ValueError("Invalid local account password hash")
    return config


def save_config(path: Path, config: dict):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Restrictive mode before writing, including when replacing an existing config.
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}")
    try:
        with os.fdopen(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as stream:
            json.dump(config, stream, indent=2)
            stream.write("\n")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--add-user", action="store_true", help="Add an account without changing the signing key")
    args = parser.parse_args()
    config = read_config(CONFIG) if CONFIG.exists() else None
    if config and not args.add_user:
        print("Local sign-in is configured. Starting backend at http://localhost:" + os.getenv("PORT", "8000"))
        return
    if not sys.stdin.isatty():
        raise SystemExit("First-time account setup needs a terminal. Run make backend in your terminal.")
    print("Create a local sign-in account. Your password will be stored only as a salted hash.")
    email = input("Work email: ").strip().lower()
    if not email or "@" not in email:
        raise SystemExit("Enter a work email address.")
    if config and any(user["email"] == email for user in config["users"]):
        raise SystemExit("This account already exists. No changes made.")
    name = input("Display name: ").strip()
    role = input("Role [coordinator / lead / physician] (coordinator): ").strip() or "coordinator"
    if not name or role not in {"coordinator", "lead", "physician"}:
        raise SystemExit("Enter a display name and one of the listed roles.")
    physician_id = input("Physician ID: ").strip() if role == "physician" else None
    if role == "physician" and not physician_id:
        raise SystemExit("Physician accounts need a physician ID.")
    password = getpass.getpass("Password (at least 8 characters): ")
    if len(password) < 8 or len(password) > 1024:
        raise SystemExit("Use a password between 8 and 1024 characters.")
    if password != getpass.getpass("Confirm password: "):
        raise SystemExit("Passwords don't match. No changes made.")
    config = config or {"secret": secrets.token_urlsafe(48), "users": []}
    config["users"].append({"email": email, "name": name, "role": role,
                            "physician_id": physician_id, "password_hash": hash_password(password)})
    save_config(CONFIG, config)
    print("Local account saved. Sign in with the email and password you just chose.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        raise SystemExit(f"Local setup failed: {error}") from None
