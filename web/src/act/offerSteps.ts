import { clockTime } from "./time.ts";
import type { Offer, OfferState } from "./types.ts";

export type Step = { label: string; detail: string; status: "done" | "current" | "todo" };

const ANSWERED: OfferState[] = ["Accepted", "Declined", "Expired", "Withdrawn", "Cancelled", "Already filled"];

// Turns the server's offer state into the five progress steps shown on the tracker.
export function offerSteps(offer: Offer, timeLeft: string | null): Step[] {
  const decided = offer.state !== "Proposed";
  const answered = ANSWERED.includes(offer.state);
  return [
    { label: "Found", detail: `${offer.proposed_by} · ${clockTime(offer.proposed_at)}`, status: "done" },
    { label: `Checked ${offer.checked_count} people`, detail: `${offer.physician_name} eligible`, status: "done" },
    {
      label: "Your decision",
      detail: !decided ? "Approve to send it" : offer.state === "Rejected" ? "Rejected" : `Approved by ${offer.approved_by ?? "lead"}`,
      status: decided ? "done" : "current",
    },
    {
      label: "Answer",
      detail: answered ? offer.state : offer.state === "Sent" && timeLeft ? `${timeLeft} to reply` : "Waits for a reply",
      status: answered ? "done" : offer.state === "Sent" ? "current" : "todo",
    },
    { label: "Re-check", detail: "Coverage after the answer", status: offer.state === "Accepted" ? "current" : "todo" },
  ];
}

export function stateBadge(state: OfferState): { text: string; tone: "amber" | "teal" | "green" | "red" | "neutral" } {
  switch (state) {
    case "Proposed": return { text: "Waiting for you", tone: "amber" };
    case "Approved":
    case "Sent": return { text: state, tone: "teal" };
    case "Accepted": return { text: state, tone: "green" };
    case "Rejected":
    case "Declined":
    case "Expired": return { text: state, tone: "red" };
    default: return { text: state, tone: "neutral" };
  }
}

export const isOpen = (offer: Offer) => !ANSWERED.includes(offer.state) && offer.state !== "Rejected";
