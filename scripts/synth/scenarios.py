"""Authored lifecycles and answers, independent of backend replay/detection code.

Times are elapsed minutes relative to the requested snapshot. Final stages,
activity and counts are declared here, not inferred by calling the application.
"""
from zoneinfo import ZoneInfo


def stalled_stroke(b):
    c = b.consult(0, None, "Stroke", [(-25, "consult_received"), (-24, "consult_triaged"),
                    (-20, "routing_attempt_failed"), (-15, "routing_attempt_failed"), (-10, "routing_attempt_failed")], "Triaged", -24)
    b.scenario("stalled_stroke", [c], "Critical ownerless stroke; three failed routes", {"routing_failures": 3})


def hospital_surge(b):
    ids = [b.consult(0, None, "Stroke", [(-35 + i * 3, "consult_received"), (-34 + i * 3, "consult_triaged")], "Triaged", -34 + i * 3) for i in range(5)]
    b.scenario("hospital_surge", ids, "Weekend baseline is unknown" if b.now.astimezone(ZoneInfo("America/New_York")).weekday() >= 5
               else "Trailing distinct receipts exceed the weekday p90", {"hospital_id": b.hid(0), "baseline_p90": 3})


def shift_end_notes(b):
    ids = []
    for p in (0, 1):
        ids.append(b.consult(p, p, "General Neuro", [(-45, "consult_received"), (-44, "consult_triaged"), (-43, "physician_assigned"),
            (-42, "incoming_call_started"), (-38, "incoming_call_ended"), (-35, "note_started")], "Documentation", -35, calls=1))
        b.activity[p] = "Documentation / Note"
    b.scenario("shift_end_notes", ids, "Two physicians end in 40 minutes with open documentation", {"physician_ids": [b.pid(0), b.pid(1)], "minutes_to_shift_end": 40})


def unavailable_owner(b):
    c = b.consult(2, 2, "Stroke", [(-30, "consult_received"), (-29, "consult_triaged"), (-28, "physician_assigned")], "Assigned", -28)
    b.signal(2, "physician_status_changed", -12, "Self-reported status: Temporarily Unavailable")
    b.status[2], b.activity[2] = "Temporarily Unavailable", "Temporarily Unavailable"
    b.scenario("unavailable_owner", [c], "Assigned stroke is stranded with an unavailable owner", {"physician_id": b.pid(2)})


def external_camera(b):
    b.signal(3, "camera_active", -15)
    b.activity[3] = "Camera Active - No Synapse Session"
    b.scenario("external_camera", [], "Camera active without a Synapse call or video", {"physician_id": b.pid(3)})


def offline_available(b):
    b.signal(4, "agent_heartbeat_lost", -10)
    b.agent[4] = "Offline"
    b.scenario("offline_available", [], "Available status with offline agent is unverified", {"physician_id": b.pid(4)})


def late_video(b):
    c = b.consult(5, 5, "Stroke", [(-24, "consult_received"), (-23, "consult_triaged"), (-22, "physician_assigned"),
        (-21, "incoming_call_started"), (-19, "incoming_call_ended", "Call ends"), (-18, "imaging_requested"), (-16, "imaging_returned"),
        (-14, "video_started", None, -1), (-4, "video_ended")], "Note Pending", -4, calls=1)
    b.scenario("late_video", [c], "Late start repairs an earlier-delivered end; stage uses event time", {"current_stage": "Note Pending"})


def exact_duplicate(b):
    c = b.consult(6, None, "General Neuro", [(-11, "consult_received")], "Received", -11)
    original = b.events[-1]
    duplicate = dict(original, ingested_at=b.stamp(-2))
    b.events.append(duplicate)
    b.duplicates.append(original["event_id"])
    b.scenario("exact_duplicate", [c], "Duplicate event ID does not add a consult", {"event_id": original["event_id"]})


def credential_imbalance(b):
    ids = []
    for i in range(5):
        ids.append(b.consult(6, 6, "General Neuro", [(-180 + i * 15, "consult_received"), (-179 + i * 15, "consult_triaged"),
            (-178 + i * 15, "physician_assigned"), (-177 + i * 15, "incoming_call_started"), (-173 + i * 15, "incoming_call_ended"),
            (-172 + i * 15, "note_started"), (-169 + i * 15, "note_signed")], "Signed Off", -169 + i * 15, calls=1))
    b.scenario("credential_imbalance", ids, "One physician carries five completed consults at a restricted site", {"physician_id": b.pid(6), "consults_this_shift": 5})


def ringing_busy(b):
    c = b.consult(7, 7, "Stroke", [(-9, "consult_received"), (-8, "consult_triaged"), (-7, "physician_assigned"), (-6, "incoming_call_ringing")], "Assigned", -7)
    busy = b.consult(8, 8, "Stroke", [(-20, "consult_received"), (-19, "consult_triaged"), (-18, "physician_assigned"),
        (-17, "incoming_call_started"), (-15, "incoming_call_ended", "Call ends"), (-14, "imaging_requested"), (-12, "imaging_returned"),
        (-10, "video_started")], "Video Consult In Progress", -10, calls=1)
    b.activity[8] = "Video Consult In Progress"
    b.consult(9, 9, "General Neuro", [(-8, "consult_received"), (-7, "consult_triaged"), (-6, "physician_assigned"),
        (-5, "incoming_call_started")], "Provider Contacted", -5, calls=1)
    b.activity[9] = "Incoming Hospital Call"
    b.signal(10, "physician_status_changed", -5, "Self-reported status: Temporarily Unavailable")
    b.status[10] = b.activity[10] = "Temporarily Unavailable"
    b.signal(11, "camera_active", -5)
    b.activity[11] = "Camera Active - No Synapse Session"
    b.scenario("ringing_busy", [c, busy], "Ringing is unresolved while seven of twelve physicians are busy or ringing", {"ringing_physician_id": b.pid(7)})


def only_one_eligible(b):
    b.scenario("only_one_eligible", [], "One roster physician passes all R1–R8; eight others each fail one rule", {
        "physician_id": b.pid(12), "proposal": {"start": b.stamp(0), "end": b.stamp(120), "hospitals": [b.hid(0)]},
        "failure_by_physician": dict(zip((b.pid(i) for i in range(13, 21)), ("opted_in", "credentialed_at_gap", "rest_at_start_at_least_10h",
            "trailing7d_plus_offer_at_most_60h", "no_schedule_overlap", "useful_duration_at_least_2h", "no_open_offer", "weekly_offer_count_below_3")))})


def complete_lifecycle(b):
    # A separately authored closed consult covers outgoing calls and camera reset.
    jitter = b.random.randrange(-5, 6)
    timeline = [(-90, "consult_received"), (-89, "consult_triaged"), (-88, "physician_assigned"),
        (-87, "incoming_call_ringing"), (-86, "incoming_call_started"), (-84, "incoming_call_ended", "Call ends"),
        (-83, "outgoing_call_started"), (-81, "outgoing_call_ended"), (-80, "imaging_requested"), (-78, "imaging_returned"),
        (-77, "video_started"), (-72, "video_ended"), (-71, "note_started"), (-65, "note_signed")]
    b.consult(0, 0, "Stroke", [(minute + jitter, *rest) for minute, *rest in timeline], "Signed Off", -65 + jitter, calls=2)


def dst_session(b):
    # 01:20 EDT -> 01:20 EST, sixty real minutes; no ambiguous time-only endpoints.
    c = b.consult(1, 1, "Stroke", [(-370, "consult_received"), (-369, "consult_triaged"), (-368, "physician_assigned"),
        (-360, "video_started"), (-300, "video_ended"), (-299, "note_started"), (-290, "note_signed")], "Signed Off", -290)
    b.scenario("dst_session", [c], "Repeated wall-clock hour is sixty elapsed minutes; weekend baseline is unknown", {"duration_minutes": 60})


ALL = (stalled_stroke, hospital_surge, shift_end_notes, unavailable_owner, external_camera,
       offline_available, late_video, exact_duplicate, credential_imbalance, ringing_busy, only_one_eligible)
