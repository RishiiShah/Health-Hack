# Mobile demo script

Draft from contract section 11 (v1.1). Anything marked `TODO(screens)` depends on Hitanshu's UI and gets filled in at rehearsal; `TODO(backend)` waits on the backend owner.

The story: the lead approves one broadcast, two physicians race for the Suncrest 19:00 gap, one wins, the lead sees it happen. Then a second broadcast nobody answers, which becomes **Missed**. Last, Shah's phone shows an on-shift physician's view.

## Data and clock

Run on the **track's** data (the `data/` folder), never on `sevaro_dataset/`. The demo clock is fixed at **Tue 17 March, 18:20 ET**. The app never uses the phone's clock; every time and countdown comes from the server's `server_now`.

| Who | Email (password `demo`) | Role in the demo |
| --- | --- | --- |
| Clinical lead on duty | `lead@demo.sevaro` | Approves the broadcast, watches coverage |
| Dr. Grace Okafor, PHY-009 | `okafor@demo.sevaro` | The one off-shift physician who passes every rule for Suncrest at 19:00 |
| Dr. Lucy Brennan, PHY-013 | `brennan@demo.sevaro` | Opted out; fails **only R1**. Opts in live and becomes the second recipient |
| Dr. Priya Shah, PHY-005 | `shah@demo.sevaro` | On shift until 20:00. Shows My shift |

The gap: **Suncrest Medical Pavilion (SYN-005), 19:00–23:00 ET**, 4 h, needs 2, has 1.

What the lead's candidate list shows at the start (this matches the brief's answer key):

| Physician | Result | Why |
| --- | --- | --- |
| Okafor | Eligible, rank 1 | Passes R1–R8 |
| Brennan | Not eligible | R1: opted out of split shifts. Everything else passes: credentialed at Suncrest, 23 h rested, 52 of 60 h with this offer, no overlap, online in 20 min |
| Alvarez | Not eligible | Not credentialed at Suncrest |
| Cho | Not eligible | Already scheduled at 19:00 |
| Haddad | Not eligible | Not opted in |
| Menon | Not eligible | 63 h this week, over the 60 h limit |

## Before you start (10 minutes)

1. **Reset the backend** to the 18:20 start (see [Reset](#reset)).
2. **Check the backend against the contract** from a laptop. Every row must be ✓:
   ```
   cd mobile
   flutter test integration/contract_check_test.dart --dart-define-from-file=config/live.json
   ```
3. **Devices.** Four phones, or four browser windows (use a separate window or private tab per person, because the session token lives in `sessionStorage` per tab). At least **one Android phone** for vibration (Okafor's, ideally). iPhone shows the chime and the title badge but never vibrates.
4. **Open the live link** on each: `https://<live-app>.vercel.app`. TODO: fill in the Vercel URL.
5. **Sign in** on each device with its email and password `demo`.
6. **Enable sound on Okafor's and Brennan's phones** and on the lead's: Account tab → **Enable sound**. Browsers only allow audio after a tap, so the chime will not play without this. Turn the phones' ringers up. `TODO(screens)`: confirm the button label and where it sits.
7. Put the lead's phone on **Approvals** and Okafor's and Brennan's on the **Offers** tab. Shah's phone on **My shift**.
8. Optional: a QR code for each physician (`https://<live-app>.vercel.app/?token=<session token>&offer=<offer id>`) to show the "opened by link" path. TODO(backend): how demo tokens are issued; contract section 9 says real sign-in links are deferred.

## The run

### 1. The lead sees the gap (lead's phone)

**Do:** nothing yet. Open **Approvals**.

**Expect:**
- Header "Tue 17 Mar · 18:2x ET" and "Approvals · 1 waiting" (or the count from `pendingCount`).
- One proposal card: Suncrest, gap at 19:00, recipient line "Dr. Okafor for Suncrest", 4 h.
- The before/after table: without the offer 1 of 2 from 19:00, with it 2 of 2.
- Open the card → **See all candidates** shows the table above: Okafor passes all eight rules; the other five each fail one, with the reason.
- Trap check shows **pass**.
- `TODO(screens)`: exact card text, section order, and where "See all candidates" sits.

**Say:** "One physician, Okafor, is eligible. Everyone else is excluded, with a reason you can read."

### 2. Brennan opts in (Brennan's phone)

**Do:**
1. Account tab → turn **Available for extra shifts** on.

**Expect:**
- The switch stays on after the server confirms (the app does not show it on before the server says so).
- Within one poll (5 s) the lead's candidate list shows **two eligible**: Okafor rank 1, Brennan rank 2. Brennan's R1 now passes.
- On the lead's phone the proposal now reads "2 physicians for Suncrest" and the button reads **Approve and send to 2 physicians**.
- `TODO(screens)`: whether the lead's open card refreshes live or needs a pull. `TODO(backend)`: the proposal must be rebuilt (or rebuilt on read) when Brennan opts in; contract 5.1 says recipients are fixed when the proposal is built, so confirm the backend rebuilds it.

**Say:** "Brennan wasn't available. She flips one switch, and within seconds the lead has a second candidate."

### 3. The lead approves (lead's phone)

**Do:**
1. Open the proposal → **Approve and send to 2 physicians** → confirm.

**Expect:**
- The lead's phone shows "approved", with no skipped recipients.
- **Okafor's and Brennan's phones both** show the simulated lock-screen takeover within one poll (5 s): "Okafor's phone · off shift · simulated", a notification "Extra shift tonight at Suncrest · 19:00 to 23:00 ET, approved by your clinical lead. Please answer within 10 min." Chime plays, and an Android phone vibrates. The browser tab title becomes "(1) New coverage request".
- The lead's **Sent** section lists both recipients, each with a countdown from 10:00.
- `TODO(screens)`: lock-screen layout; how the countdown reads.

### 4. Both tap Accept (Okafor's and Brennan's phones)

**Do:** on both phones, tap the notification → **Accept, I'll cover it** → confirm. Do it at nearly the same time.

**Expect:** exactly one winner.
- **The winner:** "Confirmed. You're on at Suncrest Medical Pavilion tonight." Hours 19:00–23:00 ET, "Sign in by 18:55", "You'll only be routed Suncrest Medical Pavilion consults during these hours", "Suncrest now shows 2 of 2 from 19:00", the next steps list (18:50 reminder, 19:00 consults start, 23:00 shift ends).
- **The other:** "Already filled, thank you." Nothing changed on their schedule.
- **The lead:** a toast "Dr. <winner> accepted · Suncrest 19:00–23:00 ET" and a chime. The **Sent** list shows one filled and the other withdrawn. In **Coverage**, Suncrest turns **2/2** at 19:00.
- The winner could be either physician; the demo works both ways. `TODO(screens)`: both end-state screens, the toast, and the Coverage cell.

**Say:** "Both got the offer at the same instant. The server decided in one transaction. The loser was told right away and nothing changed for them."

### 5. The expiry run

The 10-minute rule: an offer nobody answers becomes **Missed**.

1. **Reset** the backend (see [Reset](#reset)), so the Suncrest gap is open again with its proposal.
2. Repeat steps 2–3 (or only step 3 with Okafor alone).
3. **Nobody taps.** Watch the countdown on the physician's phone: 10:00 → 0:00.
4. At 0:00 both buttons disable and the screen shows **Expiring…** until the next poll. Then:
   - The physician sees **Missed**: "This request expired at 18:35 ET without a response." There is no penalty wording.
   - The lead's **Sent** list shows the offers expired, and the broadcast **Unfilled**.
5. Optional: a physician who taps Accept in the last second gets **Missed** with "Your response arrived after the request expired."

Waiting 10 real minutes is long on stage. Two ways to shorten it:
- Do the expiry run first, start the countdown, and talk through step 6 (Shah) while it runs.
- `TODO(backend)`: advance the demo clock with `POST /admin/clock` (mode and anchor per the backend's clock design). Confirm the app handles a jump: its clock follows `server_now`, so a forward jump is fine.

`TODO(screens)`: Expiring… and Missed layouts; whether the Offers tab keeps the Missed card under Recent.

### 6. Shah's phone (Shah's phone)

**Do:** sign in as Shah. Open **My shift**.

**Expect:**
- Header "Dr. Priya Shah · until 20:00".
- An update banner (for example "CON-2114, a stroke consult from Suncrest, was assigned to you.") and consult cards, each with ID, type, badge, hospital and status text, colored by level.
- Footer "1 h 36 min left · 15 consults today" (the time left comes from the server clock, so it matches whatever the demo clock says).
- Consult IDs and types appear here, because this is the on-shift view; they never appear in any offer or notification.
- `TODO(screens)`: card layout and the exact footer text.

**Say:** "A physician already on shift sees their work, not the coverage requests."

## Reset

Between runs and before the demo, reset the backend to 18:20 on 17 March.

```
curl -X POST "$API_BASE_URL/admin/reset" -H "Authorization: Bearer $ADMIN_TOKEN"
```

- `$ADMIN_TOKEN` is the backend's admin demo token. Ask the backend owner; it is never written in this repo, the app or a config file.
- `TODO(backend)`: confirm the route and auth. `/admin/reset` is in the backend scaffold (admin role only); the reset must also restore Brennan's opt-in to **off**, clear offers and re-create the Suncrest proposal. Say whether it does.
- After a reset, **reload every phone** (or sign out and in) so the feeds start clean. The apps keep nothing but the session token.
- Check the reset worked: the lead's candidate list shows one eligible physician (Okafor) and Brennan failing R1.

## If the backend is down: the fake URL

A second Vercel project serves the same app in **fake mode**: no backend, all data built in.
Open `https://<fake-app>.vercel.app`. TODO: fill in the Vercel URL.

What changes, and what to tell the room:
- **Each phone runs its own private copy of the data, in the browser.** Four phones do not share anything. When the lead approves on one phone, nobody else's phone gets an offer. Use the fake link for **one device at a time**, or one laptop with the role switcher (sign out, sign in as someone else).
- The fake demo clock starts at 18:25 and counts forward from the page load.
- After the lead approves, Okafor "answers" automatically about 15 seconds later, so the lead still sees the "accepted" toast and Coverage.
- A physician sees their open offer right after sign-in (Okafor has OFF-0007 waiting), so use Okafor's sign-in to show the lock screen, Accept, Already filled and Missed.
- **Reload the page to reset** the fake data.
- The expiry run takes 10 real minutes here too.
- The sign-in screen and every email and password are the same.

Decision rule: if the live link fails the pre-demo contract check, or a phone shows "Can't reach Sevaro" with Retry that doesn't clear, switch to the fake link and say so.

## Rehearsal checklist

- [ ] Backend reset; contract check all ✓
- [ ] Lead's candidate list shows Okafor eligible, Brennan failing only R1
- [ ] Sound enabled on lead, Okafor, Brennan
- [ ] Vibration confirmed on the Android phone
- [ ] Step 4 race run twice (once each winner)
- [ ] Expiry run timed (10:00)
- [ ] Fake URL opens on a phone over HTTPS
- [ ] Every `TODO(screens)` above filled in with Hitanshu
- [ ] Rehearsed once end to end with Hitanshu
