"""Print the Render dashboard values from the root .env. Runs locally; nothing is sent anywhere.

The database URL's sslrootcert is rewritten to the CA bundle baked into the Docker image, because a path on
this computer does not exist on Render. Quotes used in .env (for CC_USERS) are dropped: Render stores values literally.
"""
from pathlib import Path
import re

ROOT_ENV = Path(__file__).resolve().parents[1] / ".env"
IMAGE_CA = "/etc/ssl/certs/rds-global-bundle.pem"
KEYS = ("CC_DATABASE_URL", "CC_USERS", "CC_AUTH_SECRET", "ELEVENLABS_API_KEY", "ELEVENLABS_VOICE_ID")


def main():
    values = {}
    for line in ROOT_ENV.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = (part.strip() for part in line.split("=", 1))
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
                value = value[1:-1]
            values[key] = value
    if "CC_DATABASE_URL" in values:
        values["CC_DATABASE_URL"] = re.sub(r"sslrootcert=[^&]*", f"sslrootcert={IMAGE_CA}", values["CC_DATABASE_URL"])
    for key in KEYS:
        print(f"\n{key}\n{values.get(key, '(missing: leave empty only if optional)')}")


if __name__ == "__main__":
    main()
