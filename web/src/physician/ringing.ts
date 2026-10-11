import type { Offer } from "../act/types.ts";

// The offer to ring for: the first one the server marks Sent that this tab hasn't rung for and that hasn't
// expired on the server's clock. Expiry and state are the server's; this only picks what to show.
export function nextRinging(items: Offer[], rung: ReadonlySet<string>, serverNow: number): Offer | null {
  return items.find((o) => o.state === "Sent" && !rung.has(o.offer_id) && (!o.expires_at || Date.parse(o.expires_at) > serverNow)) ?? null;
}
