# Sevaro mobile

Flutter phone/web screens using shared repository interfaces for dummy or API data.

## Web design parity

The Flutter presentation follows the Overlap UI on `origin/anish` at `c0f5608`:
cream canvas, white bordered panels, teal actions, navy pill navigation, and
the two-bar Overlap mark. `lib/screens/theme.dart` holds the shared visual tokens.
Sign-in and offer cards keep the web's constrained widths; dashboard content
expands on larger screens, and navigation scrolls horizontally when needed.
Schedule bars and coverage cells use the web's semantic status colors.

Bricolage Grotesque, IBM Plex Sans, and IBM Plex Mono are bundled in
`assets/fonts/` for offline typography, with their SIL Open Font Licenses.
No font or UI package was added. Fonts originate from the Google Fonts repository.
The existing physician and lead workflows, backend role routing, permissions,
and server-clock behavior remain in place; the web landing page and coordinator
dashboard are outside the mobile app's existing screen set.

## Compare on your phone with dummy data

From `mobile/`, run:

```powershell
fvm flutter run -d R5CY70TKP4B --dart-define-from-file=config/fake.json
```

The app always opens login. In dummy-data mode, enter **any nonempty email
and password**. Choose **Physician** (default) for consults and schedule, or
**Clinical lead** for approvals, team schedule and coverage. The entered email
appears as the sample identity. No predefined account or password is required.
Sign out from Account to return to login. Live API login continues to verify
credentials with the backend and use the account's real role.

Dummy data stays in memory, with its clock pinned to 17 March 2026, 18:25 ET
so the snapshot stays stable while comparing. Restart for a fresh dataset.
The permissive credential behavior is enabled only on the app's fake service
instance; the standard fake repositories retain strict fixture authentication
for contract tests and other uses. Passwords are neither stored nor sent.

`RepositoryAuthGate` signs in through `AuthRepository` and passes the returned
identity and `AppServices` into `ServiceSession`. The shift, schedule, offer,
approval, coverage and account widgets are the same ones used by live API mode.
Switching to API repositories does not require a second set of dashboard UI.

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
role, matching web login; account identity also determines routing in dummy-data mode.

Real login opens the existing dashboard for the role returned by the backend:
physician gets My shift, Schedule, Offers and Account; lead gets Approvals,
Schedule, Coverage and Account; coordinator gets Use the web dashboard.
All dashboard requests use the same login token and live API. Missing endpoints
show errors with Retry, rather than synthetic data. Until `/me` supplies workflow
metadata, shift status and opt-in stay unknown and action permissions stay empty.
Live mode does not expose demo account choices or screen previews. **Check
session** in Account refreshes the authenticated identity using `/auth/me`.
Without `API_MODE=live`, login uses the in-memory repositories and opens the same dashboard screens with synthetic data.

## Checks

```powershell
fvm flutter test --no-pub
```

Auth tests cover wire shapes, failed login, restore, sign-out, expired sessions,
offline retry, and old-token 401 responses after a newer sign-in. The agent did
not build or launch the app during auth integration.
