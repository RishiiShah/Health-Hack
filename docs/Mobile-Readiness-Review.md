# Mobile readiness review

Reviewed 10 October 2026 on `mobile-screens`, following merge of `origin/mobile-data`.

**The non-auth mobile implementation is connected and its automated checks pass.**
Auth/startup integration and deployment are excluded by the user. Backend endpoints
will be supplied by the backend team, using the
[backend scaffold](Command%20Center%20Backend%20Scaffold.md) and
[mobile contract](Mobile-App-Contract.md). No backend implementation was added.

## Completed mobile work

- `ServiceSession` receives one AppServices/Me pair, routes from `me.role.wire`,
  starts the appropriate feeds, refreshes physician Me every 60 seconds, opens
  an initial offer, and removes its nested routes/dialogs on session termination.
- Physician pages consume offers/notifications, shift, schedule, preferences,
  server-clock ticks, action results, and later feed transitions. Accepted,
  declined, missed, filled, closed, and released states use returned data.
- Lead pages consume queue, proposals, broadcasts, candidates with all eight
  rules, trap checks, audit, escalation, coverage and selected-date schedules.
  Confirmations, typed rejection, permissions, skipped recipients, already-decided
  outcomes, and answer toasts are connected.
- Tab-owned polling stops on disposal. Browser feeds pause when hidden and
  refresh on visibility. Old in-flight responses are discarded after a feed
  session restarts, preventing one user's data appearing in another session.
- Errors have Retry or action feedback; stale feeds retain data with a notice.
  Actions wait for returned outcomes; counts, names, intervals and statuses are
  supplied by the repositories. The role switch on sign-in still changes copy only.
- Reference bottom dock and colored timeline remain; physician timeline highlights
  `is_you`. Timeline width now stays within its card at large text sizes.
- Debug **Open working demo** connects Chandan's existing FakeServices to these
  screens. Its four accounts share one fake backend within the workspace.
  **Preview screens** remains an independent design gallery.

## Task-document status

| Document / tasks | Status |
| --- | --- |
| Chandan 1–4, 6–10: repositories, samples, parsing, HTTP, clock, feeds, retry | Implemented; automated data tests pass |
| Chandan 5: authentication | Existing repository code retained; entry/startup integration deferred |
| Chandan 11: web alerts | Connected to notifications and Account; real phone/browser check pending |
| Chandan 12: build/deploy | Excluded; no build or deployment performed |
| Chandan 13: demo script | Local taps/results documented; live rehearsal awaits backend/auth/deployment |
| Hitanshu 1–3: startup/sign-in/router | Theme/loader/role/session shell implemented; real auth, restore and entry integration deferred |
| Hitanshu 4–14: physician, lead, error workflows | Connected to shared repositories and feeds; automated workflow checks pass |
| Hitanshu 15: accessibility | Semantics and selected 390px/200% layout tests pass; manual screen-reader/device review pending |

The original interface blocks were updated to `FeedState<T>`, `me` and
`refreshMe()`. Enum adapters use `.wire`; time labels use `formatEtLabel` or
`formatEtRange`. JSON samples live in `mobile/assets/contracts/`, rather than
`docs/contracts/`; the restored shared contract records that location.

## Verification

- `flutter test --no-pub`: **131 tests passed**, including merged data tests,
  existing UI tests, 15 connected workflow tests and 3 feed-session regressions.
- Dart static analysis covers `lib`, `test`, and `integration`.
- No app build, app launch, live backend request, deployment, or manual device
  test performed. The live contract checker was not executed against a server.
- No commit, push, or merge to `mobile` performed.

## Run and review before merging

From `mobile/`, run your normal FVM command targeting the connected phone:

```powershell
fvm flutter run -d R5CY70TKP4B
```

Hot restart if the app was already open. On sign-in tap **Open working demo**,
then select Clinical lead or a physician. See [demo-mobile.md](demo-mobile.md)
for the role flows. The top banner explicitly identifies synthetic demo data.

Check all tabs, offer confirmations/results, preference cancellation, candidates,
rejection, escalation, coverage markers, and schedules on your phone. Repeat with
large text and a screen reader. The contract targets Flutter web: chime/vibration
and browser-title behavior must also be checked in phone Chrome. Native Android
currently uses recording alert stubs and in-memory sessions; its sound button
explains this limitation.

## Work intentionally remaining

1. Auth owner connects `AppServices.fromEnvironment()`, `currentUser()`, sign-in
   and restore to `ServiceSession`; handles the excluded real token/link work.
   Debug working-demo access is absent from release/profile runs.
2. Backend team supplies/verifies non-auth mobile endpoints, authoritative
   broadcast/release behavior, repeat-safe mutations and CORS. The current backend
   scaffold alone does not establish that those endpoints are deployed.
3. User completes phone/accessibility checks; web alerts require a real browser.
4. Build/deployment owner configures the live URL, publishes web versions, and
   rehearses the shared four-device race/expiry script against the live backend.

This branch is suitable for the user's review and integration merge after the
phone pass. It is not a deployed or authenticated production app yet.

## Auth integration update — 10 October 2026

The earlier auth-deferred status above is superseded for sign-in/session behavior.
The merged web-joy backend now serves `/auth/login` and `/auth/me` with account
identity. `BackendAuthRepository` and `BackendAuthGate` connect these exact shapes
to the phone app when `API_MODE=live`, including server messages, restore,
sign-out, periodic/resume session validation and 401 handling. Older requests
cannot clear a newer session token. The default debug workflow demo remains separate.

Successful real login shows the verified account; the backend still lacks mobile
workflow endpoints and richer Me metadata. The auth adapter does not fabricate
those fields or treat demo workflows as live data. Native sessions are in memory;
browser sessions restore within their tab. Android debug HTTP is enabled for
local USB testing. See [mobile/README.md](../mobile/README.md) for commands.

Local `/health` responds successfully, and `/ready` reports authentication enabled.
No real account password or token was read or used by the agent. Tests use synthetic
HTTP responses; the user's phone test verifies their account end to end.
No Git commands, backend changes, app builds, app launches or deployment performed.

Latest mobile verification: **139 tests passed** (8 new backend-auth tests), and
`dart analyze lib test integration` reports no issues.
# Live login dashboard routing update

Live login now mounts the existing ServiceSession dashboard using the backend
account role: physician maps to physician, lead maps to clinical_lead, and
coordinator gets the web dashboard guidance. The dashboard repositories share
the authenticated API client and token. Sign-out or any authenticated 401 removes
the dashboard and nested routes. Live mode has no demo account selector.

The account identity bridge leaves shift status, opt-in, counts and permissions
unknown until GET /me supplies the mobile contract. Missing workflow endpoints
show Retry errors; no sample workflow data is injected into live sessions.
The Account tab retains its existing controls and includes Check session.

Validation: static analysis clean; all 141 mobile tests passed, including role
tab restrictions, coordinator isolation, authenticated shift rendering, expired
sessions and sign-out. No builds, app launches or Git commands were run.

