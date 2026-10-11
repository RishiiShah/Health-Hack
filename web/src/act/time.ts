// Display-only time helpers. The supplied rosters and baselines are in Eastern time, so screens show ET.
export const DISPLAY_ZONE = "America/New_York";

const hourMinute = new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZone: DISPLAY_ZONE });
const hourMinuteSecond = new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23", timeZone: DISPLAY_ZONE });
const dayMonth = new Intl.DateTimeFormat("en-GB", { weekday: "short", day: "numeric", month: "short", timeZone: DISPLAY_ZONE });

export const clockTime = (iso: string) => hourMinute.format(new Date(iso));
export const clockTimeSeconds = (iso: string | number) => hourMinuteSecond.format(new Date(iso));
export const headerDate = (iso: string | number) => dayMonth.format(new Date(iso)).replace(",", "");

// The server's clock, advanced locally between snapshots unless it is fixed.
export function serverNow(snapshotNow: string, mode: string, receivedAt: number, localNow: number): number {
  const base = Date.parse(snapshotNow);
  return mode === "fixed" ? base : base + Math.max(0, localNow - receivedAt);
}

// The first whole minute strictly after `ms`, as ISO.
export function nextMinute(ms: number): string {
  return new Date(Math.floor(ms / 60_000) * 60_000 + 60_000).toISOString();
}

export function minutesUntil(iso: string, now: number): number {
  return Math.floor((Date.parse(iso) - now) / 60_000);
}

export function duration(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  return minutes ? `${minutes} min ${seconds % 60} s` : `${seconds} s`;
}

// "HH:MM" Eastern on the same ET date as `reference`, as ISO with that date's offset.
export function etTimeOn(reference: string, hhmm: string): string {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-US", { year: "numeric", month: "2-digit", day: "2-digit", timeZoneName: "longOffset", timeZone: DISPLAY_ZONE })
      .formatToParts(new Date(reference))
      .map((p) => [p.type, p.value]),
  );
  const offset = parts.timeZoneName === "GMT" ? "+00:00" : parts.timeZoneName.slice(3);
  return `${parts.year}-${parts.month}-${parts.day}T${hhmm}:00${offset}`;
}

export function countdown(expiresAt: string, now: number): string {
  const seconds = Math.max(0, Math.ceil((Date.parse(expiresAt) - now) / 1000));
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}
