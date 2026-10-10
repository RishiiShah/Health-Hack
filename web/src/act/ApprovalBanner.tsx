import { clockTime } from "./time.ts";
import type { Offer } from "./types.ts";
import "./act.css";

export function ApprovalBanner({ pending, onReview }: { pending: Offer[]; onReview: () => void }) {
  if (!pending.length) return null;
  const first = pending[0];
  return (
    <div className="approval-banner">
      <div>
        <h1>{pending.length} {pending.length === 1 ? "offer" : "offers"} waiting for your approval</h1>
        <p>
          {first.hospital_names.join(", ")}, {clockTime(first.start)} to {clockTime(first.end)}: approve or reject the off-shift
          offer for {first.physician_name}. Once you approve, it goes straight to their app.
        </p>
      </div>
      <button className="btn primary" onClick={onReview}>Review the offer</button>
    </div>
  );
}
