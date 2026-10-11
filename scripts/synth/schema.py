"""sample-csv-v1 column contract; credential columns use generated hospital IDs."""
VERSION = "1.0"
HEADERS = {
    "hospitals": "hospital_id,hospital_name,local_timezone,coverage_tier",
    "physicians_on_shift": "physician_id,name,shift_start_et,shift_end_et,split_shift_opt_in",
    "physicians_off_shift_roster": "physician_id,name,role,split_shift_opt_in,last_shift_end,next_shift_start,hours_worked_last_7d,est_minutes_to_online,preferred_channel,offers_declined_last_30d",
    "credentialing_matrix": "physician_id,name",
    "baseline_hourly_volume": "hospital_id,hospital_name,dow_type,hour_start_et,mean_consults,p90_consults,weeks_sampled",
    "coverage_requirements": "hospital_id,hospital_name,time_block_et,min_available_credentialed_physicians",
    "event_stream": "event_id,event_time,ingested_at,consult_id,event_type,physician_id,hospital_id,description",
    "snapshot_physicians": "physician_id,name,shift_et,self_reported_status,desktop_agent,derived_state,consults_this_shift,calls_this_shift,open_consults,minutes_to_shift_end",
    "snapshot_open_consults": "consult_id,hospital_id,hospital_name,physician_id,consult_type,current_stage,stage_entered_at,minutes_in_stage,minutes_since_received",
}
DESCRIPTIONS = {
    "consult_received": "Stroke consult request received",
    "consult_triaged": "Consult triaged",
    "physician_assigned": "Physician assigned",
    "incoming_call_ringing": "Incoming hospital call ringing",
    "incoming_call_started": "Incoming hospital call started",
    "incoming_call_ended": "Call ends; phone-only consult (outside treatment window)",
    "outgoing_call_started": "Outgoing hospital call started",
    "outgoing_call_ended": "Call ends",
    "imaging_requested": "Imaging requested",
    "imaging_returned": "Imaging returned",
    "video_started": "Video started",
    "video_ended": "Video ended",
    "note_started": "Note started",
    "note_signed": "Note signed",
    "routing_attempt_failed": "No available credentialed provider; retry scheduled",
    "physician_status_changed": "Self-reported status: Available",
    "camera_active": "Camera active",
    "camera_inactive": "Camera inactive",
    "agent_heartbeat_lost": "Agent heartbeat lost",
    "shift_started": "Shift started",
}
STATUSES = ("Available", "In Meeting", "Temporarily Unavailable")
ZONES = ("America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles")
STAGES = ("Received", "Triaged", "Assigned", "Provider Contacted", "CT/CTA or Imaging Pending", "Imaging Review", "Video Consult In Progress", "Note Pending", "Documentation", "Signed Off")
TRANSITIONS = dict(zip(("consult_received", "consult_triaged", "physician_assigned", "incoming_call_started", "imaging_requested", "imaging_returned", "video_started", "video_ended", "note_started", "note_signed"), STAGES))
EXTENSIONS = ("next_shift_end", "offers_sent_last_7d", "open_offer")


def headers(name, hospitals=(), extended=False):
    columns = HEADERS[name].split(",")
    if name == "credentialing_matrix":
        columns += list(hospitals)
    if name == "physicians_off_shift_roster" and extended:
        columns += list(EXTENSIONS)
    return columns
