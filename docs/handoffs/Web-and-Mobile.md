# Web and mobile handoff

2026-10-11; fix commit `9fe1333`, branch `rishi`. Joy's `web-joy` at `6b4d090`
was already merged by `37bb1e4`; this cohort did not introduce another branch merge.

## Delivered and verified

- Sign-in labels now name email/password fields and expose role selection. Actual account permissions remain server-controlled.
- Physician shift view reads `on_shift`; accepted coverage shows “Awaiting arrival,” then “On shift” only after an observed arrival event. Optional fallback preserves the existing presentation-demo DTO.
- Landing page describes implemented deterministic decision support, the fixed kit and reviewed offers. Removed unsupported AI/SLA, outcome and compliance claims; map is illustrative and weekend baseline is visibly missing.
- Real CSV file uploads preserve byte checksum, official references, existing histories and durable receipts. Compatible events change decisions; the incompatible development namespace is held and explained.
- Real multi-role offer loop and workspace navigation passed in Chrome. Web tests **58 passed** and production build passed. Desktop and 390 px checks found no page overflow/errors in the tested routes.
- Mobile tests **149 passed**, analyzer clean, Flutter web build passed. Mobile already respects attendance; no mobile runtime patch was needed for the shift-status fix.

## Next actionable work

1. Run the supported mobile offer/auth/data contracts on actual Android/iOS against a staging backend. Test token expiry, connectivity loss, retry, navigation cancellation and physician ownership; record device/OS and API commit.
2. Verify real authorized offer audio and failure handling after staging speech configuration. This cohort disabled external speech; browser offer success does not prove provider playback.
3. When a weekend scenario API exists, add an explicitly selected scenario view/export with provenance and unknown staffing. Keep the official Data section unchanged and never turn scenario results into operational actions.

Broadcasts, mobile schedule/preferences/release, and automatic critical-item
announcements remain outside implemented live scope. Do not present fake/demo
screens as implemented production endpoints. See [mobile contract scope](../Mobile-App-Contract.md).

Run `npm test` and `npm run build` in `web`; run `flutter analyze`,
`flutter test` and `flutter build web` in `mobile`. Use the existing compatible
SDK and dependencies. Run both browser scripts in the order specified by the
[E2E audit](../E2E-Audit-2026-10-11.md). They are fresh-fixture localhost tests,
not production checks. The narrow dark-text design exception is documented there.
