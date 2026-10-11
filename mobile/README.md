# Sevaro mobile

Flutter phone/web screens, shared data repositories and a debug workflow demo.

## Test real auth on the connected Android phone

Keep your PC backend running at `http://localhost:8000`, with auth configured.
Use your account created with `python scripts/setup_auth.py`, rather than the
mobile demo credentials (unless you explicitly configured those accounts).

In PowerShell, from this `mobile/` directory:

```powershell
& "D:\Local\Android\Sdk\platform-tools\adb.exe" -s R5CY70TKP4B reverse tcp:8000 tcp:8000
fvm flutter run -d R5CY70TKP4B --dart-define=API_MODE=live --dart-define=API_BASE_URL=http://127.0.0.1:8000
```

This ADB path matches this checkout's SDK. Re-run reverse after reconnecting the
phone. Debug Android allows local HTTP; release retains normal HTTPS defaults.
Stop/restart Flutter when changing Dart defines; hot reload does not change them.

1. Wrong password: server's “Email or password is incorrect.” message; email retained.
2. Correct password: **Signed in to the backend**, returned name, email, role and physician ID.
3. **Check session** calls `/auth/me`; a 401 returns to sign-in. Validation also runs
   every 60 seconds while active, and when the app resumes.
4. **Sign out** clears the token and returns to sign-in; sign in again to repeat.
5. Stop the backend and Check session: connection error without losing the token.
   Restart the backend and Check session again to recover.

Native session storage is currently in memory: a full restart requires sign-in.
Browser session storage restores through `/auth/me` on reload. Passwords are not
stored; tokens are not displayed.

## Auth boundary

The backend returns `{token, expires_at, user}` from `/auth/login`, and `{user}`
from `/auth/me`. Roles: coordinator, lead, physician. The phone auth adapter parses
these separately from mobile Me; it does not invent permissions, shift, preference
or count fields that the backend does not supply.

Live login asks for email and password only. The backend account determines the
role, matching web login; the role selector remains in design previews only.

Real login opens the existing dashboard for the role returned by the backend:
physician gets My shift, Schedule, Offers and Account; lead gets Approvals,
Schedule, Coverage and Account; coordinator gets Use the web dashboard.
All dashboard requests use the same login token and live API. Missing endpoints
show errors with Retry, rather than synthetic data. Until `/me` supplies workflow
metadata, shift status and opt-in stay unknown and action permissions stay empty.
Live mode does not expose demo account choices or screen previews. **Check
session** in Account refreshes the authenticated identity using `/auth/me`.
Without `API_MODE=live`, the existing debug demo/gallery entry remains available.

## Checks

```powershell
fvm flutter test --no-pub
```

Auth tests cover wire shapes, failed login, restore, sign-out, expired sessions,
offline retry, and old-token 401 responses after a newer sign-in. The agent did
not build or launch the app during auth integration.
