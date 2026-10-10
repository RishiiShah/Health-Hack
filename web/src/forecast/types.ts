// Snapshot sections for the forecast screens, as proposed in docs/Web-Joy.md. Replace with types.gen.ts once the backend serves them.
export type CellStatus = "gap" | "at_minimum" | "above_minimum" | "unknown";

export type CoverageCell = {
  at: string;
  count: number | null;
  required: number | null;
  status: CellStatus;
  unverified: boolean;
  schedule_incomplete: boolean;
  physician_ids: string[];
  incomplete_physician_ids: string[];
  gap_id: string | null;
};

export type Coverage = {
  supported: boolean;
  steps?: string[];
  assumption?: string | null;
  hospitals?: { hospital_id: string; hospital_name: string; nobody_reachable_now: boolean; cells: CoverageCell[] }[];
};

export type Demand = {
  supported: boolean;
  items?: { hospital_id: string; hospital_name: string; trailing_60m: number; p90: number | null; status: "surge" | "normal" | "unknown" }[];
};

export type Level = "Critical" | "Warning" | null;

export type Workload = {
  supported: boolean;
  items?: {
    physician_id: string;
    name: string;
    consults: number;
    calls: number;
    open_consults: number;
    shift_end: string | null;
    minutes_to_shift_end: number | null;
    overload: Level;
    shift_end_risk: Level;
    open_notes: number;
    reason: string;
  }[];
};
