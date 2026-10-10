**Owns:** `mobile/lib/data/*`, `mobile/lib/audio.dart`, the build and deploy config, `mobile/test/data/*`, and the shared JSON samples in `docs/contracts/mobile_offer_*.json`.

### Tasks
1. `OfferRepository` interface: `getOffer`, `accept` and `decline`, each taking a token. A `FakeOfferRepository` for Hitanshu's tests → check: Hitanshu's tests run with no network.
2. `HttpOfferRepository` using `package:http` against the `/m/offer*` endpoints → check: it parses all the sample JSON files.
3. `OfferDto`: parse each field explicitly. An unknown state or a missing field is an error, never a silent default → check: unit tests with bad JSON.
4. Polling: every 5 s while the offer is Sent, stop once it reaches an end state, and refresh when the tab becomes visible again → check: a unit test with a fake timer.
5. Clock-difference correction: compute the countdown from the server's `server_now` and `expires_at`, not the phone's clock → check: the countdown is correct with the phone clock set wrong.
6. Repeated-tap safety: a retried accept after a network error must return the same result (the backend makes this safe to repeat; agree it with them) → check: a scripted retry.
7. Audio: a "Listen to offer" button using `package:web`'s `HTMLAudioElement` with `src=/m/offer/audio?token=…`. Never autoplays; the button hides on 503 → check: plays on a phone, hidden when the API key is removed.
8. Config: `--dart-define=API_BASE_URL=…` → check: the build points at the deployed backend.
9. Deploy the Flutter web build as a static site on Vercel. Send the origin to the backend owner to add to the server's allowed-origins (CORS) list → check: the link opens on a phone over HTTPS.
10. Demo script (`docs/demo-mobile.md`): two phones with different physician tokens accept for the same gap, so one gets "Already filled"; plus one expiry run → check: rehearsed once end to end.

**Out of scope:** state-management, audio or Firebase plugins, storing anything on the phone, and native app-store builds.
