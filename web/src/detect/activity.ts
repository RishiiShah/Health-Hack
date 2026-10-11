import type { Consult, Physician } from "./types.ts";

// Counts describe the published snapshot; physician activity and consult stages are independent.
export function activitySummary(physicians: Physician[], consults: Consult[]) {
  return {
    video: physicians.filter((p) => p.derived === "Video Consult" || p.derived === "Video Consult In Progress").length,
    calls: physicians.filter((p) => ["Hospital Call", "Incoming Hospital Call", "Outgoing Hospital Call"].includes(p.derived)).length,
    documentation: consults.filter((c) => ["Note Pending", "Documentation"].includes(c.stage)).length,
    imagingReview: consults.filter((c) => c.stage === "Imaging Review").length,
    imagingPending: consults.filter((c) => ["Imaging Pending", "CT/CTA or Imaging Pending"].includes(c.stage)).length,
  };
}

export function elapsed(minutes: number) {
  const seconds = Math.max(0, Math.floor(minutes * 60 + 1e-7));
  return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}
