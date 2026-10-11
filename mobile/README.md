# Cerevia mobile

Flutter phone/web screens, shared data repositories and a debug workflow demo.
This release checkout includes the team mobile source from `origin/mobile`
commit `35cc674` plus the verified existing-backend adapter. Backend and web
source remain from `rishi`; older backend/web files from the mobile branch were
not copied. Current scope and policy differences are in [document authority](../docs/README.md).

## Web design parity

The Flutter presentation uses the current Cerevia web design tokens: slate ECG-paper
canvas, pale bordered surfaces, ice-blue primary actions, compact rectangular
navigation, and the two-bar Cerevia mark. `lib/screens/theme.dart` owns the
shared palette, typography, fields and controls for live and demo screens.
The demo Command page follows the web's Triage → Coverage outlook → Dispatch
reading order. Headers wrap on phones, wide tables scroll inside their cards,
and table rows grow to accommodate content. Existing role permissions, data
sources and approval workflows are unchanged. This update matches the web's
light palette; Flutter does not yet expose the web's dark-mode toggle.

Responsive regression checks in `test/screens/design_parity_test.dart` cover
390 × 844 portrait and 844 × 390 landscape layouts, including navigation to
the dashboard and horizontal scrolling in coverage tables.

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

Keep your local backend running at `http://localhost:8000`, with auth configured.
Use your account created with `python scripts/setup_auth.py`, rather than the
mobile demo credentials (unless you explicitly configured those accounts).

With Flutter **3.35.3** and Android platform-tools on your path, from `mobile/`:

```sh
adb devices
adb -s DEVICE_ID reverse tcp:8000 tcp:8000
flutter run -d DEVICE_ID --dart-define=API_MODE=live --dart-define=API_BASE_URL=http://127.0.0.1:8000
```

Replace `DEVICE_ID` with the connected device shown by `adb devices`. Re-run
reverse after reconnecting. Debug Android allows local HTTP; release retains normal HTTPS defaults.
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

## Auth and workflow boundary

The backend returns `{token, expires_at, user}` from `/auth/login`, and `{user}`
from `/auth/me`. Roles: coordinator, lead, physician. The phone auth adapter parses
these separately from mobile Me. `BackendApiClient` adapts the implemented backend
routes and response shapes to the screen DTOs. Workflow metadata comes from `/me`;
role `lead` maps to `clinical_lead`, and screen permission names map only from the
server's granted permissions. The server still authorizes every request.

Live login asks for email and password only. The backend account determines the
role, matching web login; account identity also determines routing in dummy-data mode.

Real login opens the existing dashboard for the role returned by the backend:
physician gets My shift, Schedule, Offers and Account; lead gets Approvals,
Schedule, Coverage and Account; coordinator gets Use the web dashboard.
All dashboard requests use the same login token and live API. The supported live
workflows are own shift/consults, sent offers and replies, lead proposals and
approvals/rejections, candidates, trap checks, audits, escalation authorization,
offer responses, and coverage. One backend offer is one recipient; the backend
selects subsequent candidates sequentially. It does not broadcast the mobile
design contract's whole recipient set.

Schedule views, preference updates and release are outside this integration.
They display an explicit unavailable-capability message; schedule views do not
offer a futile Retry. The preference switch and release button are disabled or
absent. Unknown counts and ranks stay nullable; missing simulator evidence is
shown as unavailable, never replaced with a passing verdict or zero-valued evidence.
The shift counter label says “this shift,” matching the server's actual counters.
Offer activity is derived from real sent-offer records; the badge means actionable
offers, with no stored read receipts. Paused backend clocks stay paused on mobile.

Live mode does not expose demo account choices or screen previews. **Check
session** in Account refreshes the authenticated identity using `/auth/me`.
Without `API_MODE=live`, login uses the in-memory repositories and opens the same dashboard screens with synthetic data.

## Checks

```sh
flutter pub get --enforce-lockfile
flutter analyze --no-pub
flutter test --no-pub
flutter build web --release --no-pub --dart-define=API_MODE=live --dart-define=API_BASE_URL=https://YOUR-API-GATEWAY
flutter build web --release --no-pub --dart-define=API_MODE=fake
```

Verified with the existing documented Flutter 3.35.3 / Dart 3.9.2 toolchain:
`flutter analyze --no-pub` is clean, all 166 tests pass, and
`flutter build web --release --no-pub --dart-define=API_MODE=live --dart-define=API_BASE_URL=https://backend.example`
succeeds. No packages or lockfile versions changed. This verifies the Flutter web
build; it does not constitute a physical Android/iOS device test or deployment.

`test/data/backend_client_test.dart` exercises the real native payload shapes,
paths, bearer auth, retries, conflicts, cancellation reasons, server time and
capability messages. Its fixture is exported from actual synthetic API calls by
`backend/tests/test_mobile_contract.py` in the decision-engine checkout, with no
challenge CSVs, answer keys or credentials. The backend test compares current
responses to `backend/tests/fixtures/mobile_backend.json`; the same bundle is
stored at `mobile/test/fixtures/backend_workflows.json`. To intentionally update
it, run the backend test with `CC_MOBILE_FIXTURE_OUTPUT=/tmp/mobile_backend.json`,
copy the output to both fixture paths, then rerun both suites. The older mobile
v1.1 samples and `LiveServices` contract tests remain for design/demo workflows;
production `API_MODE=live` enters `BackendAuthGate` and uses `BackendApiClient`.

The backend currently has no cross-origin CORS policy. A Flutter web deployment
needs an API gateway on the same origin, forwarding the authenticated API paths,
or a separately reviewed restricted CORS configuration. Compiling with an example
HTTPS URL checks the build, not reachability or hosted-browser sign-in. Do not
point an Android phone's localhost at the desktop without ADB reverse or another
explicit network route. The Render endpoint has not been provisioned in this step.
