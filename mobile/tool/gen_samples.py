"""Generate assets/contracts/mobile_*.json (contract v1.1, section 10) from the track's data,
plus lib/data/fake/fake_samples.g.dart so the fakes embed exactly the same JSON.

Run from mobile/:  python3 tool/gen_samples.py

Track data used (data/ folder, not sevaro_dataset/):
  Okafor PHY-009 eligible (credentialed at SYN-005, last shift ended 07:00, 36 h in 7 d, online in 15 min)
  Brennan PHY-013 fails only R1 (opted out), Alvarez PHY-010 not credentialed at SYN-005,
  Cho PHY-011 scheduled 19:00, Haddad PHY-012 opted out, Menon PHY-014 59 h + 4 h = 63 h.
  Shah PHY-005 on shift 08:00-20:00, 15 consults, 18 calls, credentialed at 5 hospitals,
  open consults CON-2104 (Meadowlands) and CON-2113 (Suncrest).
Demo clock: 17 March 2026, 18:20-18:30 ET.
"""
import copy, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "contracts"
DART = ROOT / "lib" / "data" / "fake" / "fake_samples.g.dart"


def t(hm, day=17):
    return f"2026-03-{day:02d}T{hm}-04:00"


SUN = {"hospital_id": "SYN-005", "name": "Suncrest Medical Pavilion"}
MEADOW = {"hospital_id": "SYN-004", "name": "Meadowlands Community Hospital"}
NORTH = {"hospital_id": "SYN-008", "name": "Northfield Medical"}
OAK = {"hospital_id": "SYN-010", "name": "Oak Valley Medical"}

# ---------------------------------------------------------------- Me
ME_OKAFOR = {
    "user_id": "okafor@demo.sevaro", "role": "physician", "display_name": "Dr. Grace Okafor",
    "physician_id": "PHY-009", "permissions": ["offer.respond", "preferences.update"],
    "split_shift_opt_in": True, "offers_received_7d": 2, "weekly_offer_limit": 3,
    "on_shift": False, "shift_end": None, "server_now": t("18:20:00"),
}
ME_BRENNAN = {**ME_OKAFOR, "user_id": "brennan@demo.sevaro", "display_name": "Dr. Lucy Brennan",
              "physician_id": "PHY-013", "split_shift_opt_in": False, "offers_received_7d": 0}
ME_SHAH = {**ME_OKAFOR, "user_id": "shah@demo.sevaro", "display_name": "Dr. Priya Shah",
           "physician_id": "PHY-005", "split_shift_opt_in": None, "offers_received_7d": 0,
           "on_shift": True, "shift_end": t("20:00:00")}
ME_LEAD = {
    "user_id": "lead@demo.sevaro", "role": "clinical_lead", "display_name": "Clinical lead on duty",
    "physician_id": None,
    "permissions": ["proposal.approve", "proposal.reject", "escalation.authorize", "audit.read"],
    "split_shift_opt_in": None, "offers_received_7d": None, "weekly_offer_limit": None,
    "on_shift": None, "shift_end": None, "server_now": t("18:20:00"),
}

# ---------------------------------------------------------------- Offers
WHY_OKAFOR = ["Credentialed at Suncrest", "12 h rested since your last shift",
              "40 of 60 h this week, so you stay under the limit"]


def offer(**kw):
    base = {
        "offer_id": "OFF-0007", "gap_id": "GAP-SYN-005-1900", "hospitals": [SUN],
        "start": t("19:00:00"), "end": t("23:00:00"), "hours": 4.0,
        "reason": "You are credentialed at Suncrest Medical Pavilion and available tonight.",
        "status": "sent", "status_reason": None,
        "sent_at": t("18:25:00"), "expires_at": t("18:35:00"), "responded_at": None,
        "routing_hospitals": [SUN],
        "approved_at": t("18:24:00"),
        "gap_summary": "Suncrest will be one physician short from 19:00. You'd be the second.",
        "sign_in_by": t("18:55:00"),
        "why_you": WHY_OKAFOR,
        "allowed_actions": ["accept", "decline"],
        "next_steps": [], "coverage_after": None,
    }
    base.update(kw)
    return base


NEXT_STEPS = [
    {"at": t("18:50:00"), "label": "Reminder to sign in"},
    {"at": t("19:00:00"), "label": "Suncrest consults start routing to you"},
    {"at": t("23:00:00"), "label": "Shift ends"},
]
COVERAGE_AFTER = {"staffed": 2, "required": 2, "from": t("19:00:00")}

OFFER_SENT = offer()
OFFER_ACCEPTED = offer(status="accepted", responded_at=t("18:27:10"), allowed_actions=["release"],
                       next_steps=NEXT_STEPS, coverage_after=COVERAGE_AFTER)


def past(offer_id, gap, hosp, day, start, end, sent, **kw):
    return offer(offer_id=offer_id, gap_id=gap, hospitals=[hosp], routing_hospitals=[hosp],
                 start=t(start, day), end=t(end, day if end > start else day + 1),
                 hours=4.0, sent_at=t(sent, day), approved_at=t(sent, day),
                 expires_at=t(sent[:3] + f"{int(sent[3:5]) + 10:02d}" + sent[5:], day),
                 sign_in_by=t(f"{int(start[:2]) - 1:02d}:55:00", day),
                 reason=f"You are credentialed at {hosp['name']}.",
                 gap_summary=f"{hosp['name']} was one physician short.",
                 why_you=[f"Credentialed at {hosp['name']}"],
                 allowed_actions=[], **kw)


OFFERS = {
    "offers": [
        OFFER_SENT,
        past("OFF-0006", "GAP-SYN-008-1300", NORTH, 16, "13:00:00", "17:00:00", "12:20:00",
             status="released", responded_at=t("12:24:00", 16)),
        past("OFF-0005", "GAP-SYN-004-1900", MEADOW, 15, "19:00:00", "23:00:00", "18:20:00",
             status="accepted", responded_at=t("18:23:00", 15)),
        past("OFF-0004", "GAP-SYN-010-1500", OAK, 14, "15:00:00", "19:00:00", "14:20:00",
             status="declined", responded_at=t("14:22:00", 14)),
        past("OFF-0003", "GAP-SYN-005-1600", SUN, 13, "16:00:00", "20:00:00", "15:10:00",
             status="expired"),
        past("OFF-0002", "GAP-SYN-008-1900", NORTH, 12, "19:00:00", "23:00:00", "18:15:00",
             status="withdrawn", status_reason="filled_by_another_physician"),
        past("OFF-0001", "GAP-SYN-004-1900", MEADOW, 11, "19:00:00", "23:00:00", "18:05:00",
             status="withdrawn", status_reason="gap_closed"),
    ],
    "server_now": t("18:25:04"),
}

# ---------------------------------------------------------------- Action results
def action(outcome, applied, off, now):
    return {"outcome": outcome, "applied": applied, "offer": off, "server_now": t(now)}


ACCEPT_ACCEPTED = action("accepted", True, OFFER_ACCEPTED, "18:27:10")
ACCEPT_FILLED = action("already_filled", False,
                       offer(status="withdrawn", status_reason="filled_by_another_physician",
                             allowed_actions=[]), "18:27:12")
ACCEPT_EXPIRED = action("expired", False, offer(status="expired", allowed_actions=[]), "18:35:02")
DECLINE_DECLINED = action("declined", True,
                          offer(status="declined", responded_at=t("18:26:30"), allowed_actions=[]),
                          "18:26:30")
RELEASE_RELEASED = action("released", True,
                          offer(status="released", responded_at=t("18:27:10"), allowed_actions=[]),
                          "18:29:00")

PREFS_UPDATED = {"applied": True, "outcome": "updated", "open_offer_id": None,
                 "me": {**ME_BRENNAN, "split_shift_opt_in": True, "server_now": t("18:22:30")},
                 "server_now": t("18:22:30")}
PREFS_OPEN = {"applied": False, "outcome": "open_offer_exists", "open_offer_id": "OFF-0007",
              "me": {**ME_OKAFOR, "server_now": t("18:26:00")}, "server_now": t("18:26:00")}

# ---------------------------------------------------------------- Lead
ESCALATION = {
    "escalation_id": "ESC-0002", "hospital_name": "Oak Valley Medical",
    "reason": "Stroke consult unassigned 10 min; every credentialed physician busy.",
    "proposed_intervention": "Clinical lead to contact Dr. Kim to take the consult after his current call.",
    "status": "pending", "created_at": t("18:18:00"), "authorized_by": None, "authorized_at": None,
}

LEAD_QUEUE = {
    "pending_count": 2,
    "proposals": [{
        "proposal_id": "PRP-0003", "gap_id": "GAP-SYN-005-1900", "hospitals": [SUN],
        "start": t("19:00:00"), "end": t("23:00:00"), "recipient_count": 1,
        "proposed_at": t("18:21:00"),
    }],
    "escalations": [ESCALATION],
    "automated_actions": [{"at": t("18:19:30"), "text": "Re-routed CON-2105 at Oak Valley"}],
    "server_now": t("18:22:00"),
}

EXCLUDED = [
    {"physician_id": "PHY-010", "display_name": "Dr. Ben Alvarez", "failed_rule": "R2",
     "detail": "Not credentialed at Suncrest Medical Pavilion"},
    {"physician_id": "PHY-011", "display_name": "Dr. Hannah Cho", "failed_rule": "R5",
     "detail": "Already scheduled from 19:00"},
    {"physician_id": "PHY-012", "display_name": "Dr. Omar Haddad", "failed_rule": "R1",
     "detail": "Opted out of split shifts"},
    {"physician_id": "PHY-013", "display_name": "Dr. Lucy Brennan", "failed_rule": "R1",
     "detail": "Opted out of split shifts"},
    {"physician_id": "PHY-014", "display_name": "Dr. Ravi Menon", "failed_rule": "R4",
     "detail": "63 h in 7 days with this offer, limit 60"},
]
TRAP_EXPLANATION = ("Joiner limited to Suncrest and seeded at 12 consults; gap closes, "
                    "no other hospital worsens.")
PROPOSAL = {
    "proposal_id": "PRP-0003", "gap_id": "GAP-SYN-005-1900",
    "gap": {"hospitals": [SUN], "start": t("19:00:00"), "end": t("23:00:00"), "hours": 4.0,
            "required": 2, "counted": 1, "shortfall": 1},
    "recipients": [{"physician_id": "PHY-009", "display_name": "Dr. Grace Okafor", "rank": 1,
                    "rank_reason": "Covers the gap hospital, online in 15 min, 1 decline in 30 days"}],
    "excluded": EXCLUDED,
    "trap_check": {"result": "pass", "explanation": TRAP_EXPLANATION},
    "coverage_preview": {
        "times": [t("19:00:00"), t("19:15:00"), t("19:30:00")],
        "without": [{"staffed": 1, "required": 2}] * 3,
        "with": [{"staffed": 2, "required": 2}] * 3,
    },
    "status": "proposed", "proposed_by": "Coordinator on duty", "proposed_at": t("18:21:00"),
    "decided_by": None, "decided_at": None, "reject_reason": None,
    "server_now": t("18:22:00"),
}
PROPOSAL_APPROVED = {
    "outcome": "approved", "applied": True,
    "proposal": {**PROPOSAL, "status": "approved", "decided_by": "Clinical lead on duty",
                 "decided_at": t("18:24:00"), "server_now": t("18:24:00")},
    "offers": [{"offer_id": "OFF-0007", "physician_id": "PHY-009", "status": "sent"}],
    "skipped": [], "server_now": t("18:24:00"),
}
PROPOSAL_ALREADY = {
    "outcome": "already_decided", "applied": False,
    "proposal": {**PROPOSAL, "status": "rejected", "decided_by": "Clinical lead on duty",
                 "decided_at": t("18:23:00"), "reject_reason": "Cho can stay late instead",
                 "server_now": t("18:24:10")},
    "offers": [], "skipped": [], "server_now": t("18:24:10"),
}


def rules(r1, r2, r3, r4, r5, r6, r7=(True, "No other open offer"), r8=(True, "Fewer than 3 offers this week")):
    names = ["Opted in", "Credentialed where needed", "Rested", "Weekly hours", "No overlap",
             "Long enough", "One open offer", "Weekly offer limit"]
    return [{"rule": f"R{i + 1}", "name": names[i], "passed": p, "detail": d}
            for i, (p, d) in enumerate([r1, r2, r3, r4, r5, r6, r7, r8])]


OPT_IN = (True, "Opted in to split shifts")
OPT_OUT = (False, "Opted out of split shifts")
CRED = (True, "Credentialed at Suncrest Medical Pavilion")
NOCRED = (False, "Not credentialed at Suncrest Medical Pavilion")
CANDIDATES = {
    "gap_id": "GAP-SYN-005-1900", "evaluated_at": t("18:21:00"),
    "candidates": [
        {"physician_id": "PHY-009", "display_name": "Dr. Grace Okafor", "eligible": True, "rank": 1,
         "rules": rules(OPT_IN, CRED, (True, "12 h since last shift"), (True, "40 of 60 h with this offer"),
                        (True, "Next shift Wed 18 Mar 19:00"), (True, "4 h; online in 15 min"))},
        {"physician_id": "PHY-010", "display_name": "Dr. Ben Alvarez", "eligible": False, "rank": None,
         "rules": rules(OPT_IN, NOCRED, (True, "23 h since last shift"), (True, "28 of 60 h with this offer"),
                        (True, "Next shift Thu 19 Mar 08:00"), (True, "4 h; online in 10 min"))},
        {"physician_id": "PHY-011", "display_name": "Dr. Hannah Cho", "eligible": False, "rank": None,
         "rules": rules(OPT_IN, CRED, (True, "12 h since last shift"), (True, "52 of 60 h with this offer"),
                        (False, "Already scheduled from 19:00"), (True, "4 h; online now"))},
        {"physician_id": "PHY-012", "display_name": "Dr. Omar Haddad", "eligible": False, "rank": None,
         "rules": rules(OPT_OUT, NOCRED, (True, "35 h since last shift"), (True, "40 of 60 h with this offer"),
                        (False, "Already scheduled from 20:00"), (True, "4 h; online now"))},
        {"physician_id": "PHY-013", "display_name": "Dr. Lucy Brennan", "eligible": False, "rank": None,
         "rules": rules(OPT_OUT, CRED, (True, "23 h since last shift"), (True, "52 of 60 h with this offer"),
                        (True, "Next shift Wed 18 Mar 08:00"), (True, "4 h; online in 20 min"))},
        {"physician_id": "PHY-014", "display_name": "Dr. Ravi Menon", "eligible": False, "rank": None,
         "rules": rules(OPT_IN, CRED, (True, "23 h since last shift"), (False, "63 h in 7 days with this offer, limit 60"),
                        (True, "Next shift Thu 19 Mar 07:00"), (True, "4 h; online in 40 min"))},
    ],
    "server_now": t("18:22:00"),
}

TRAP_CHECK = {"gap_id": "GAP-SYN-005-1900", "result": "pass", "explanation": TRAP_EXPLANATION,
              "seed_consults": 12, "joiner_projected_consults": 3,
              "busiest_peer_projected_consults": 5, "server_now": t("18:22:00")}

LEAD_OFFERS = {
    "broadcasts": [{
        "proposal_id": "PRP-0003", "gap_id": "GAP-SYN-005-1900", "hospitals": [SUN],
        "start": t("19:00:00"), "end": t("23:00:00"), "status": "open", "filled_by": None,
        "offers": [{"offer_id": "OFF-0007", "physician_id": "PHY-009", "display_name": "Dr. Grace Okafor",
                    "status": "sent", "status_reason": None, "expires_at": t("18:35:00"),
                    "responded_at": None}],
    }],
    "server_now": t("18:26:00"),
}

AUDIT = {
    "gap_id": "GAP-SYN-005-1900",
    "entries": [
        {"at": t("18:20:00"), "actor": "System", "action": "gap_detected",
         "detail": "Suncrest projected 1 of 2 from 19:00"},
        {"at": t("18:21:00"), "actor": "System", "action": "eligibility_checked",
         "detail": "6 off-shift physicians checked, 1 eligible"},
        {"at": t("18:21:00"), "actor": "Coordinator on duty", "action": "proposal_created",
         "detail": "Offer to Dr. Grace Okafor, 19:00-23:00 ET"},
        {"at": t("18:24:00"), "actor": "Clinical lead on duty", "action": "proposal_approved",
         "detail": "Sent to 1 physician"},
    ],
    "server_now": t("18:30:00"),
}

LOGIN = {"token": "demo-okafor", "me": ME_OKAFOR}

NOTIFICATIONS = {
    "items": [
        {"notification_id": "N-0012", "kind": "offer", "title": "Extra shift tonight at Suncrest",
         "body": "19:00 to 23:00 ET, approved by your clinical lead. Please answer within 10 min.",
         "at": t("18:25:00"), "offer_id": "OFF-0007", "unread": True},
        {"notification_id": "N-0009", "kind": "schedule", "title": "Cerevia",
         "body": "Your next shift: Wed 18 Mar, 19:00.", "at": t("08:02:00", 16),
         "offer_id": None, "unread": False},
    ],
    "server_now": t("18:25:04"),
}

SHIFT_ON = {
    "on_shift": True, "shift_start": t("08:00:00"), "shift_end": t("20:00:00"),
    "consults_today": 15, "calls_today": 18, "hospitals_count": 5,
    "update": {"text": "CON-2113, a stroke consult from Suncrest, has a note due.", "at": t("18:19:00")},
    "consults": [
        {"consult_id": "CON-2104", "consult_type": "Stroke", "hospital_name": "Meadowlands Community Hospital",
         "badge": "New", "status_text": "Provider contacted 6 min ago", "level": "critical"},
        {"consult_id": "CON-2113", "consult_type": "Stroke", "hospital_name": "Suncrest Medical Pavilion",
         "badge": "Note due", "status_text": "Note open 8 of 30 min", "level": "warning"},
    ],
    "next_shift": None, "server_now": t("18:20:00"),
}
SHIFT_OFF = {
    "on_shift": False, "shift_start": None, "shift_end": None,
    "consults_today": 0, "calls_today": 0, "hospitals_count": 0, "update": None, "consults": [],
    "next_shift": {"start": t("19:00:00", 18), "end": t("07:00:00", 19)},
    "server_now": t("18:20:00"),
}
SCHEDULE = {
    "week_start": "2026-03-15",
    "days": [{"date": "2026-03-15", "kind": "off"}, {"date": "2026-03-16", "kind": "day"},
             {"date": "2026-03-17", "kind": "day"}, {"date": "2026-03-18", "kind": "day"},
             {"date": "2026-03-19", "kind": "off"}, {"date": "2026-03-20", "kind": "day"},
             {"date": "2026-03-21", "kind": "off"}],
    "today": {"status": "on_shift", "start": t("08:00:00"), "end": t("20:00:00"),
              "consults": 15, "calls": 18, "hospitals": 5},
    "with_you": {
        "hospital_name": "Suncrest Medical Pavilion",
        "window_start": t("06:00:00"), "window_end": t("00:00:00", 18),
        "rows": [
            {"display_name": "Ramirez", "label": "to 19:00", "start": t("07:00:00"), "end": t("19:00:00"), "is_you": False},
            {"display_name": "Lee", "label": "to 19:00", "start": t("07:00:00"), "end": t("19:00:00"), "is_you": False},
            {"display_name": "You", "label": "to 20:00", "start": t("08:00:00"), "end": t("20:00:00"), "is_you": True},
        ],
        "note": "From 19:00 you're the only confirmed physician here. Your clinical lead is arranging a second.",
    },
    "next_shift": {"start": t("08:00:00", 18), "end": t("20:00:00", 18)},
    "server_now": t("18:20:00"),
}

COVERAGE = {
    "columns": [{"label": "Now", "at": t("18:22:00")}, {"label": "19:00", "at": t("19:00:00")},
                {"label": "19:45", "at": t("19:45:00")}],
    "hospitals": [
        {"hospital_id": "SYN-005", "name": "Suncrest", "status_text": "Short at 19:00 · offer out", "level": "short",
         "cells": [{"staffed": 3, "required": 2, "marker": None}, {"staffed": 1, "required": 2, "marker": "*"},
                   {"staffed": 1, "required": 1, "marker": None}]},
        {"hospital_id": "SYN-010", "name": "Oak Valley", "status_text": "No one free for stroke", "level": "no_one_free",
         "cells": [{"staffed": 1, "required": 1, "marker": None}, {"staffed": 1, "required": 1, "marker": None},
                   {"staffed": 1, "required": 1, "marker": None}]},
        {"hospital_id": "SYN-009", "name": "Lakeview", "status_text": "At minimum", "level": "at_minimum",
         "cells": [{"staffed": 3, "required": 1, "marker": None}, {"staffed": 1, "required": 1, "marker": None},
                   {"staffed": 1, "required": 1, "marker": None}]},
        {"hospital_id": "SYN-008", "name": "Northfield", "status_text": "Covered", "level": "covered",
         "cells": [{"staffed": 5, "required": 2, "marker": None}, {"staffed": 3, "required": 2, "marker": None},
                   {"staffed": 3, "required": 2, "marker": None}]},
    ],
    "footnotes": [{"marker": "*", "text": "Counts Dr. Cho, who is scheduled from 19:00 but not signed in yet."}],
    "server_now": t("18:22:00"),
}
LEAD_SCHEDULE = {
    "date": "2026-03-17",
    "banner": {"text": "Suncrest short at 19:00. Offer waiting.", "proposal_id": "PRP-0003"},
    "window_start": t("12:00:00"), "window_end": t("00:00:00", 18),
    "on_shift": [
        {"physician_id": pid, "display_name": n, "kind": "day", "start": t(s), "end": t(e)}
        for pid, n, s, e in [("PHY-001", "Patel", "08:00:00", "20:00:00"), ("PHY-002", "Kim", "08:00:00", "20:00:00"),
                             ("PHY-003", "Ramirez", "07:00:00", "19:00:00"), ("PHY-004", "Brooks", "09:00:00", "21:00:00"),
                             ("PHY-005", "Shah", "08:00:00", "20:00:00"), ("PHY-006", "Lee", "07:00:00", "19:00:00"),
                             ("PHY-007", "Torres", "10:00:00", "22:00:00"), ("PHY-008", "Williams", "08:00:00", "20:00:00")]
    ],
    "off_shift": [
        {"physician_id": "PHY-009", "display_name": "Okafor", "kind": "offer", "start": t("19:00:00"), "end": t("23:00:00")},
        {"physician_id": "PHY-010", "display_name": "Alvarez", "kind": "away", "start": None, "end": None},
        {"physician_id": "PHY-011", "display_name": "Cho", "kind": "night", "start": t("19:00:00"), "end": t("07:00:00", 18)},
        {"physician_id": "PHY-012", "display_name": "Haddad", "kind": "night", "start": t("20:00:00"), "end": t("08:00:00", 18)},
        {"physician_id": "PHY-013", "display_name": "Brennan", "kind": "away", "start": None, "end": None},
        {"physician_id": "PHY-014", "display_name": "Menon", "kind": "away", "start": None, "end": None},
    ],
    "off_shift_working_today": 3, "off_shift_total": 6,
    "server_now": t("18:22:00"),
}

ERR_401 = {"error": {"code": "unauthorized", "message": "Wrong email or password."}}
ERR_403 = {"error": {"code": "forbidden", "message": "Only the clinical lead on duty can approve offers."}}

FILES = {
    "mobile_me_physician.json": ME_OKAFOR,
    "mobile_me_lead.json": ME_LEAD,
    "mobile_me_shah.json": ME_SHAH,
    "mobile_me_brennan.json": ME_BRENNAN,
    "mobile_offers.json": OFFERS,
    "mobile_offer_accept_accepted.json": ACCEPT_ACCEPTED,
    "mobile_offer_accept_already_filled.json": ACCEPT_FILLED,
    "mobile_offer_accept_expired.json": ACCEPT_EXPIRED,
    "mobile_offer_decline_declined.json": DECLINE_DECLINED,
    "mobile_offer_release_released.json": RELEASE_RELEASED,
    "mobile_preferences_updated.json": PREFS_UPDATED,
    "mobile_preferences_open_offer.json": PREFS_OPEN,
    "mobile_lead_queue.json": LEAD_QUEUE,
    "mobile_proposal.json": PROPOSAL,
    "mobile_proposal_approved.json": PROPOSAL_APPROVED,
    "mobile_proposal_already_decided.json": PROPOSAL_ALREADY,
    "mobile_candidates.json": CANDIDATES,
    "mobile_trap_check.json": TRAP_CHECK,
    "mobile_lead_offers.json": LEAD_OFFERS,
    "mobile_audit.json": AUDIT,
    "mobile_escalation.json": ESCALATION,
    "mobile_login.json": LOGIN,
    "mobile_notifications.json": NOTIFICATIONS,
    "mobile_shift_on.json": SHIFT_ON,
    "mobile_shift_off.json": SHIFT_OFF,
    "mobile_schedule.json": SCHEDULE,
    "mobile_lead_coverage.json": COVERAGE,
    "mobile_lead_schedule.json": LEAD_SCHEDULE,
    "mobile_error_401.json": ERR_401,
    "mobile_error_403.json": ERR_403,
}

# bad/: each must fail to parse as the named schema (the schema is in the file name).
bad_role = copy.deepcopy(ME_LEAD); bad_role["role"] = "nurse"
bad_status = copy.deepcopy(OFFERS); bad_status["offers"][0]["status"] = "pending"
bad_outcome = copy.deepcopy(ACCEPT_ACCEPTED); bad_outcome["outcome"] = "maybe"
bad_missing = copy.deepcopy(OFFER_SENT); del bad_missing["expires_at"]
bad_type = copy.deepcopy(ME_OKAFOR); bad_type["offers_received_7d"] = "2"
bad_null = copy.deepcopy(OFFER_SENT); bad_null["status"] = None
bad_tz = copy.deepcopy(OFFER_SENT); bad_tz["expires_at"] = "2026-03-17T18:35:00"
BAD = {
    "me__unknown_role.json": bad_role,
    "offer_list__unknown_status.json": bad_status,
    "offer_action_result__unknown_outcome.json": bad_outcome,
    "offer__missing_expires_at.json": bad_missing,
    "me__wrong_type.json": bad_type,
    "offer__null_required.json": bad_null,
    "offer__timestamp_without_offset.json": bad_tz,
}


def main():
    (OUT / "bad").mkdir(parents=True, exist_ok=True)
    for name, body in FILES.items():
        (OUT / name).write_text(json.dumps(body, indent=2, ensure_ascii=False) + "\n")
    for name, body in BAD.items():
        (OUT / "bad" / name).write_text(json.dumps(body, indent=2, ensure_ascii=False) + "\n")

    # Embed for the fakes so they work synchronously, with no asset loading.
    lines = ["// GENERATED by tool/gen_samples.py from assets/contracts/. Do not edit by hand.",
             "// ignore_for_file: lines_longer_than_80_chars", "",
             "const Map<String, String> kSamples = {"]
    for name, body in FILES.items():
        raw = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
        lines.append(f"  '{name}': r'''{raw}''',")
    lines.append("};")
    DART.parent.mkdir(parents=True, exist_ok=True)
    DART.write_text("\n".join(lines) + "\n")
    print(f"wrote {len(FILES)} samples, {len(BAD)} bad samples, and {DART.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
