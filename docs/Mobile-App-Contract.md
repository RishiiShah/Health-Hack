# Mobile App Contract

10 October 2026 · v1.1 · Chandan (data) and Hitanshu (screens)

Repository reference for the v1.1 agreement supplied by the team in the conversation.
This edition condenses its tables and examples without changing the wire fields.
Complete executable JSON examples are in `mobile/assets/contracts/`; DTOs and strict
parsers are in `mobile/lib/data/models.dart`. Update this agreement first when
changing the interface. The backend owner supplies the endpoints described here;
the [backend scaffold](Command%20Center%20Backend%20Scaffold.md) is the architecture
reference, rather than a replacement for these mobile payloads.

## 1. Decisions

- Flutter web, opened on a phone by URL/QR. Physician and clinical lead dashboards;
  coordinator/admin use the web dashboard. Native builds are outside this contract.
- Broadcast to every eligible physician; first valid acceptance fills the gap.
  Rank explains selection and does not imply sequential sending.
- Action business outcomes return HTTP 200. Errors are auth, permission, input,
  unavailable resources, and outages. Every POST/PUT is repeat-safe.
- Offer expiry is ten minutes after sending, displayed as **Missed**.
- Polling; no mobile WebSocket, push, Firebase or AI voice calls. The simulated
  coverage call plays the server's offer audio; the app never generates speech.
- Physician opt-out leaves the physician in candidates, failing R1 with
  “Opted out of split shifts”. Real sign-in links and missed-offer penalties deferred.

## 2. Conventions

`API_BASE_URL` is supplied by Dart define; authenticated requests send a Bearer
token. A 401 from an authenticated call ends the session. JSON is snake_case;
Dart is camelCase. Required fields and enums parse strictly; unknown values fail.
Only fields explicitly marked nullable may be null.

Timestamps include a UTC offset; display in Eastern with **ET**. Every response
has `server_now` (embedded records may obtain it from their enclosing response).
The live demo begins at 18:20 ET on 17 March 2026. Local fake services begin at
18:25 ET to exercise a sent offer. Countdown uses the server clock, never a
phone clock directly.

No patient data in offers, notifications, or action results. My shift alone may
show consult ID/type, hospital, and stage/status; no names, ages, or symptoms.

## 3. Endpoints

| Role | Method / path | Body / response |
| --- | --- | --- |
| Both | POST `/auth/login` | `{email, password}` → `{token, me}` |
| Both | GET `/me` | Me |
| Physician | PUT `/me/preferences` | `{split_shift_opt_in, decline_open_offer}` → PreferencesResult |
| Physician | GET `/offers` | OfferList; physician's last seven days, newest first |
| Physician | GET `/offers/{offer_id}` | Offer |
| Physician | POST `/offers/{offer_id}/accept`, `/decline`, `/release` | No body → OfferActionResult |
| Physician | GET `/notifications` | NotificationList |
| Physician | GET `/offers/{offer_id}/audio` | `audio/mpeg`, own sent offer only. Any other status (503 text-to-speech off, 409 not sent) → show the offer text, no play button |
| Physician | GET `/me/shift` | MyShift |
| Physician | GET `/me/schedule?week_start=YYYY-MM-DD` | MySchedule |
| Lead | GET `/lead/queue` | LeadQueue |
| Lead | GET `/proposals/{proposal_id}` | Proposal |
| Lead | POST `/proposals/{proposal_id}/approve` | No body → ProposalActionResult |
| Lead | POST `/proposals/{proposal_id}/reject` | `{reason}`; nonempty → ProposalActionResult |
| Lead | GET `/gaps/{gap_id}/candidates`, `/trap-check`, `/audit` | CandidateList, TrapCheck, AuditLog |
| Lead | GET `/lead/offers?active=true` | BroadcastList |
| Lead | POST `/escalations/{escalation_id}/authorize` | No body → EscalationActionResult |
| Lead | GET `/lead/coverage` | CoverageBoard |
| Lead | GET `/lead/schedule?date=YYYY-MM-DD` | LeadSchedule |

## 4. Physician schemas

### 4.1 Me

`user_id`, `role`, `display_name`, `physician_id`, `permissions`,
`split_shift_opt_in`, `offers_received_7d`, `weekly_offer_limit`, `on_shift`,
`shift_end`, `server_now`. Roles: `physician`, `clinical_lead`, `coordinator`,
`admin`. Physician ID, preference, counts, shift flag/end are nullable for
non-physicians; shift end is null off shift. Permissions gate UI actions;
the server enforces them independently.

### 4.2 Offer

`offer_id`, `gap_id`, `hospitals`, `start`, `end`, `hours`, `reason`, `status`,
`status_reason`, `sent_at`, `expires_at`, `responded_at`, `routing_hospitals`,
plus section 13.5 fields. Hospital is `{hospital_id, name}`. `status_reason`
and `responded_at` are nullable. Physician-visible statuses only:
`sent`, `accepted`, `declined`, `expired`, `withdrawn`, `released`.

### 4.3 Status presentation

| State | Label / behavior |
| --- | --- |
| sent | New request; takeover, countdown, Accept / Decline |
| accepted | You're on; start ET and routing hospitals |
| declined | Declined; “You declined this request.” |
| expired | Missed; expiry time, no penalty language |
| withdrawn + filled_by_another_physician | Already filled; another physician covered the shift |
| withdrawn + gap_closed | No longer needed |
| released | Released; clinical lead notified physician cannot make it |

### 4.4 OfferList

`{offers: Offer[], server_now}`. Home groups sent first, accepted soonest first,
then Recent for all other states.

### 4.5 OfferActionResult

`{outcome, applied, offer, server_now}`. Outcomes: `accepted`, `declined`,
`already_filled`, `expired`, `not_open`, `released`. Show the returned outcome,
never infer success from the button tapped. Expired after an acceptance attempt:
“Your response arrived after the request expired.”

Accept is atomic per gap: sent, before expiry, open gap → accepted/applied;
other open offers withdraw with `filled_by_another_physician`. Repeated acceptance
returns accepted/not applied. Withdrawn/filled → already_filled; expired or sent
at/after deadline → expired; declined → declined; withdrawn/closed → not_open.
Decline applies only to sent; repeat is declined/not applied. Other states return
their matching outcome, not applied. Decline cannot undo an accepted shift.

### 4.6 Preferences

Request `{split_shift_opt_in, decline_open_offer}`. Result
`{applied, outcome, open_offer_id, me, server_now}`; open_offer_id nullable.
`updated` applies, `unchanged` does not. Opting out with a sent offer and false
decline flag returns `open_offer_exists`, changing nothing. Confirm then resend
with `decline_open_offer: true`. A proposed but unsent offer needs no prompt.

## 5. Clinical lead schemas

### 5.1 Broadcast rules

Recipients pass R1–R8 at proposal creation, in G18 rank order. Approval rechecks
G21, skipping newly ineligible recipients with reasons. First `shortfall` valid
acceptances fill the gap atomically and withdraw remaining open offers. All
declined/expired → unfilled; a new proposal may be raised. R7 permits one open
offer per physician; R8 limits three in seven days. Each sent offer counts.
Broadcast replaces sequential G18/G22 sending, pending backend confirmation.

### 5.2 LeadQueue

`{pending_count, proposals, escalations, automated_actions, server_now}`.
Lists newest first. Proposal summary has `proposal_id`, `gap_id`, `hospitals`,
`start`, `end`, `recipient_count`, `proposed_at`. Escalations are pending.

### 5.3 Proposal

`proposal_id`, `gap_id`, `gap`, `recipients`, `excluded`, `trap_check`,
`coverage_preview`, `status`, `proposed_by`, `proposed_at`, `decided_by`,
`decided_at`, `reject_reason`, `server_now`. Decision fields nullable.
Status: `proposed`, `approved`, `rejected`, `cancelled`.

- Gap: `{hospitals, start, end, hours, required, counted, shortfall}`.
- Recipient: `{physician_id, display_name, rank, rank_reason}`.
- Excluded: `{physician_id, display_name, failed_rule, detail}`; first failed rule.
- Trap summary: `{result: pass|fail, explanation}`.
- Coverage preview: `{times, without, with}`, staffing arrays `{staffed, required}`.

### 5.4 ProposalActionResult

`{outcome, applied, proposal, offers, skipped, server_now}`. Offers are
`{offer_id, physician_id, status}`; skipped uses Excluded. `approved`/`rejected`
apply or repeat the same result with applied false. `already_decided` means
opposite decision or cancellation, no change. Empty reject reason → 422.

### 5.5 CandidateList

`{gap_id, evaluated_at, candidates, server_now}`. All six off-shift physicians,
each `{physician_id, display_name, eligible, rank, rules}`; rank nullable.
All eight rules R1–R8 in order: `{rule, name, passed, detail}`.

### 5.6 TrapCheck

`{gap_id, result, explanation, seed_consults, joiner_projected_consults,
busiest_peer_projected_consults, server_now}`. Result: pass/fail.

### 5.7 BroadcastList

`{broadcasts, server_now}`. Broadcast: `{proposal_id, gap_id, hospitals, start,
end, status, filled_by, offers}`. Status: open/filled/unfilled. Filled-by nullable
`{physician_id, display_name}`. Recipient offer: `{offer_id, physician_id,
display_name, status, status_reason, expires_at, responded_at}`; same offer enums,
nullable reason/response. Lead toast fires on a status transition between polls.

### 5.8 Escalation

`{escalation_id, hospital_name, reason, proposed_intervention, status, created_at,
authorized_by, authorized_at}`; last two nullable. Status pending/authorized.
Result `{outcome: authorized|already_authorized, applied, escalation, server_now}`.

### 5.9 Stroke risk

No stroke-risk list or `/snapshot` call on mobile v1.1; web keeps the full queue.

### 5.10 AuditLog

`{gap_id, entries, server_now}`. Entries `{at, actor, action, detail}` oldest first,
append-only. Action is display text, not an enum used for branching.

## 6. Errors

Non-2xx shape `{error: {code, message}}`. 401 unauthorized ends an authenticated
session; wrong-login credentials show on the sign-in form. 403 forbidden:
“You don't have permission for this.” 404 not_found: “This item is no longer
available.” 422 invalid_request shows message; 503 unavailable/network failure
shows Retry. Another physician's offer returns 404. Business outcomes remain 200.

## 7. Polling

| Data | Cadence |
| --- | --- |
| Physician offers + notifications | 3 s (a newly sent offer rings the simulated call) |
| Physician Me | Start, preference changes, every 60 s |
| My shift | 30 s while tab open |
| Physician schedule | Tab opens or week changes |
| Lead queue + active offers | 5 s |
| Coverage | 15 s while tab open |
| Lead schedule | Tab opens or date changes |

Stop polling hidden tabs; refresh immediately when visible. Unseen sent offer
opens simulated lock screen, chimes only after Enable sound, vibrates Android
Chrome, and updates title to “(1) New coverage request”.

## 8. Countdown

At receipt, offset = server_now − device time. Remaining = expires_at −
(device now + offset). At zero disable actions and show **Expiring…** until a
poll returns authoritative status. Never show Accepted before an accepted result.

## 9. Demo sign-in

Password `demo`, demo mode only: lead@demo.sevaro (clinical lead), shah@demo.sevaro
(PHY-005 on shift), okafor@demo.sevaro (PHY-009 off shift), brennan@demo.sevaro
(PHY-013 opts in live). QR `?token=…&offer=OFF-0007` reads token once and removes
it from address bar. Real account/token issuing deferred. Sign-in role switch
changes subtitle only; role comes from Me.

## 10. Samples

`mobile/assets/contracts/` contains Me, all offer states/results/preferences,
queue/proposal/actions, all candidates, trap/active offers/audit/escalation,
login/notifications, on/off shift/schedules/coverage, errors, and malformed
`bad/` cases. This is the implementation location of the originally proposed
`docs/contracts/`. `tool/gen_samples.py` embeds them for fakes; tests verify parity.

## 11. Demo

Use track data, not the alternative synthetic dataset: Okafor initially eligible;
Alvarez not credentialed at Suncrest; Cho overlaps; Haddad/Brennan opted out;
Menon exceeds 60 hours. Brennan fails only R1 and becomes eligible after opt-in.
Lead approves; two offers arrive; exactly one acceptance wins. Coverage becomes
2/2; second run expires; Shah shows My shift. See [demo-mobile.md](demo-mobile.md).

## 12. Open items

Backend confirms broadcast replacement, release reopening/notifying lead, and
supplies the new mobile endpoints. Release appears only in allowed_actions.
Real accounts/QR issuance and penalties deferred. Offer audio is server-generated
and played only in the simulated coverage call.
Auth and deployment excluded from the current screen completion pass.

## 13. Design additions

### 13.1 Sign-in

Email/password; wrong credentials 401 message on form. Operations covers lead,
coordinator, admin; subtitle switch never chooses role. SSO/forgot password:
“Not available in the demo”.

### 13.2 Me

`on_shift` bool nullable, `shift_end` timestamp nullable; physician header uses them.

### 13.3 MyShift

`{on_shift, shift_start, shift_end, consults_today, calls_today, hospitals_count,
update, consults, next_shift, server_now}`. Shift times/update/next_shift nullable.
Update `{text, at}`; next shift `{start, end}`. Consult `{consult_id, consult_type,
hospital_name, badge, status_text, level}`; badge nullable; level critical/warning/ok.
Off shift: empty consults, counts zero, shift fields null. Time left from server clock.

### 13.4 MySchedule

`{week_start, days, today, with_you, next_shift, server_now}`. Seven Sunday-first
days `{date, kind: day|night|off|split}`. Today `{status: on_shift|off_shift, start,
end, consults, calls, hospitals}`; times nullable. With-you nullable
`{hospital_name, window_start, window_end, rows, note}`; note nullable;
rows `{display_name, label, start, end, is_you}`. Next-shift nullable `{start, end}`;
null displays “Not in this roster yet”.

### 13.5 Offer additions / release

`approved_at`, `gap_summary`, `sign_in_by`, `why_you` string array,
`allowed_actions` subset accept/decline/release, `next_steps` array `{at, label}`,
`coverage_after` nullable `{staffed, required, from}`. Why-you replaces reason for
display, reason fallback. Accepted shift can release only when allowed, reopening
gap and telling lead. Result/status released. Decline never undoes acceptance.

### 13.6 NotificationList

`{items, server_now}`, newest first. Item `{notification_id, kind, title, body,
at, offer_id, unread}`; offer_id nullable; kinds offer/reminder/schedule/outcome.
Server writes text without patient data. New unread offer opens simulated lock
screen; tapping opens the offer.

### 13.7 Lead additions

Queue automated_actions `{at, text}`; escalations are separate approval cards.
Proposal coverage_preview as 5.3. Approve label uses recipient name for one,
recipient count for multiple.

### 13.8 CoverageBoard

`{columns, hospitals, footnotes, server_now}`. Columns `{label, at}`.
Hospital `{hospital_id, name, status_text, level, cells}`; levels short,
no_one_free, at_minimum, covered. Cells `{staffed, required, marker}`; marker
nullable. Footnotes `{marker, text}`. Keep server order.

### 13.9 LeadSchedule

`{date, banner, window_start, window_end, on_shift, off_shift,
off_shift_working_today, off_shift_total, server_now}`. Banner nullable
`{text, proposal_id}`. Shift row `{physician_id, display_name, kind, start, end}`;
kind day/night/away/offer. Off-shift start/end nullable. Banner opens proposal.
