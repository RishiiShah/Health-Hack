// Response shapes for the Decide/Act screens, as proposed in docs/Web-Joy.md. Replace with types.gen.ts once the backend serves them.
export type OfferState =
  | "Proposed" | "Approved" | "Rejected" | "Sent" | "Cancelled"
  | "Accepted" | "Already filled" | "Declined" | "Expired" | "Withdrawn";

export type Offer = {
  offer_id: string;
  gap_id: string;
  physician_id: string;
  physician_name: string;
  hospital_names: string[];
  start: string;
  end: string;
  state: OfferState;
  checked_count: number;
  proposed_by: string;
  proposed_at: string;
  approved_by: string | null;
  approved_at: string | null;
  sent_at: string | null;
  expires_at: string | null;
  responded_at: string | null;
  message: string | null;
  audio_url: string | null;
  phone_url: string | null;
  reject_reason: string | null;
};

export type Gap = {
  gap_id: string;
  hospital_ids: string[];
  hospital_names: string[];
  start: string;
  end: string;
  required: number;
  count: number;
  summary: string;
};

export type RuleResult = { rule: string; status: "pass" | "fail" | "unknown"; explanation: string };

export type Candidate = {
  physician_id: string;
  name: string;
  eligible: boolean;
  rank: number | null;
  primary_reason: string | null;
  results: RuleResult[];
  ranking: { gap_hospitals: number; minutes_to_online: number | null; declines_30d: number | null; hours_7d: number | null };
};

export type Candidates = { gap: Gap; revision: number; rules: { id: string; label: string }[]; candidates: Candidate[] };

export type TrapCheck = {
  gap_id: string;
  physician_id: string;
  passed: boolean;
  reasons: string[];
  seed_consults: number;
  limited_to: { hospital_id: string; hospital_name: string }[];
  steps: string[];
  without: { count: number; required: number }[];
  with: { count: number; required: number }[];
  joiner_load: number;
  busiest_peer_load: number;
  other_gaps_worsened: boolean;
  assumption: string;
};

export type Intervention = { intervention_id: string; kind: string; item_id: string; reason: string; created_at: string };

export type AuditEntry = { at: string; actor: string; action: string; detail: string };

export type IngestReport = {
  accepted: number;
  duplicates: number;
  conflicts: number;
  reordered: number;
  late: number;
  held_orphans: number;
  quarantined: { reason: string }[];
  revision: number;
  pending_future: number;
  clock_advanced_to?: string;
  latest_event_time?: string | null;
};

export type DataQuality = {
  supported: boolean;
  events_read?: number;
  accepted?: number;
  duplicates?: number;
  duplicate_ids?: string[];
  conflicts?: number;
  reordered?: number;
  late?: number;
  max_reorder_lag_s?: number;
  max_delivery_lag_s?: number;
  rejected?: number;
  pending_orphans?: number;
  expired_orphans?: number;
};

export type Dataset = { name: string; description: string; reference_files: number };
