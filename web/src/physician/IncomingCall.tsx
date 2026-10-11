import { useEffect, useMemo, useRef, useState } from "react";
import { playAudio, post } from "../api/client.ts";
import { useApi } from "../act/hooks.ts";
import { clockTime, countdown } from "../act/time.ts";
import type { Offer } from "../act/types.ts";
import { nextRinging } from "./ringing.ts";

// Simulated phone call: when the server sends this physician an offer, the tab rings. Answering plays the
// server's audio and asks for a reply; the server decides the outcome. Declining the call only hides it.
export function IncomingCall() {
  const [tick, setTick] = useState(0);
  const { data } = useApi<{ now: string; items: Offer[] }>("/me/offers", Math.floor(tick / 3));
  const fetchedAt = useMemo(() => Date.now(), [data]);
  const rung = useRef(new Set<string>());
  const [call, setCall] = useState<Offer | null>(null);
  const [answered, setAnswered] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const audio = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    const timer = setInterval(() => setTick((t) => t + 1), 1000);
    return () => clearInterval(timer);
  }, []);
  const now = data ? Date.parse(data.now) + (Date.now() - fetchedAt) : null;

  useEffect(() => {
    if (call || !data || now === null) return;
    const next = nextRinging(data.items, rung.current, now);
    if (!next) return;
    rung.current.add(next.offer_id);
    setCall(next);
    setAnswered(false);
    setResult(null);
  }, [data, call, now]);

  // The server may close the offer mid-call (expired, filled by someone else).
  const live = call && data?.items.find((o) => o.offer_id === call.offer_id);
  const closed = !result && live && live.state !== "Sent" ? `This offer is ${live.state.toLowerCase()}.` : null;
  const ringing = Boolean(call && !answered && !result && !closed);

  useEffect(() => (ringing ? startRing() : undefined), [ringing]);

  if (!call) return null;
  const close = () => {
    audio.current?.pause();
    setCall(null);
  };

  function answer() {
    setAnswered(true);
    // The written message is always shown, so a failed or missing recording loses nothing.
    if (call?.audio_url) playAudio(call.audio_url).then((a) => (audio.current = a), () => undefined);
  }

  async function reply(choice: "accept" | "decline") {
    try {
      const offer = await post<Offer>(`/me/offers/${encodeURIComponent(call!.offer_id)}/${choice}`);
      setResult(offer.state === "Accepted" ? `You're covering ${offer.hospital_names.join(", ")} ${clockTime(offer.start)}–${clockTime(offer.end)} ET.` : `Offer ${offer.state.toLowerCase()}.`);
    } catch (e) {
      setResult((e as Error).message);
    }
  }

  const done = result ?? closed;
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-sm">
      <section role="alertdialog" aria-labelledby="call-title" className="w-full max-w-sm rounded-3xl bg-[#161E2E] p-7 text-center text-white shadow-2xl">
        <span className="font-mono text-[11px] uppercase tracking-widest text-teal-300">{ringing ? "Incoming call" : answered ? "On call" : "Call ended"}</span>
        <h2 id="call-title" className="mt-3 text-2xl font-bold">Sevaro Coverage</h2>
        <p className="mt-1 text-sm text-slate-300">Incoming shift offer from Sevaro Operations</p>
        <div className="mt-6 rounded-2xl bg-white/10 p-4">
          <strong className="block text-lg">{call.hospital_names.join(", ")}</strong>
          <span className="font-mono text-sm text-slate-200">{clockTime(call.start)} to {clockTime(call.end)} ET</span>
          {call.expires_at && now !== null && !done && <p className="mt-2 font-mono text-xs text-amber-300">Reply within {countdown(call.expires_at, now)}</p>}
        </div>
        {answered && !done && call.message && <p className="mt-4 text-sm text-slate-200">{call.message}</p>}
        <p className="mt-3 text-[11px] text-slate-400">Synthetic demonstration · no patient details</p>
        {done ? (
          <div className="mt-6">
            <p role="status" className="rounded-xl bg-white/10 p-3 text-sm font-semibold">{done}</p>
            <button onClick={close} className="mt-4 w-full rounded-full bg-white py-3 text-sm font-semibold text-slate-900">Close</button>
          </div>
        ) : !answered ? (
          <div className="mt-8 flex justify-around">
            <button onClick={close} className="h-16 w-16 rounded-full bg-red-600 text-sm font-semibold shadow-lg">Decline</button>
            <button onClick={answer} className="h-16 w-16 animate-pulse rounded-full bg-teal-500 text-sm font-semibold shadow-lg">Answer</button>
          </div>
        ) : (
          <div className="mt-6 grid gap-2">
            <button onClick={() => reply("accept")} className="rounded-full bg-teal-500 py-3 text-sm font-semibold">Accept shift</button>
            <button onClick={() => reply("decline")} className="rounded-full bg-white/10 py-3 text-sm font-semibold">Decline shift</button>
            <button onClick={close} className="py-2 text-xs text-slate-400">Hang up · reply later from Offers</button>
          </div>
        )}
      </section>
    </div>
  );
}

// Two-tone ring from the Web Audio API, so no sound file ships. Browsers allow it after the sign-in click.
function startRing(): () => void {
  if (typeof AudioContext === "undefined") return () => undefined;
  const ctx = new AudioContext();
  const tone = (offset: number) => {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.frequency.value = 480;
    gain.gain.value = 0.08;
    osc.connect(gain).connect(ctx.destination);
    osc.start(ctx.currentTime + offset);
    osc.stop(ctx.currentTime + offset + 0.4);
  };
  const ring = () => { tone(0); tone(0.6); };
  ring();
  const timer = setInterval(ring, 2500);
  return () => { clearInterval(timer); void ctx.close(); };
}
