import { useEffect, useMemo, useRef, useState } from "react";
import { playAudio, post } from "../api/client.ts";
import { useApi } from "../act/hooks.ts";
import { clockTime, countdown } from "../act/time.ts";
import type { Offer } from "../act/types.ts";
import { nextRinging } from "./ringing.ts";
import "./physician.css";

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
    <div className="call-overlay">
      <section role="alertdialog" aria-labelledby="call-title" className="call-card">
        <span className="call-state">{ringing ? "Incoming call" : answered ? "On call" : "Call ended"}</span>
        <h2 id="call-title">Sevaro Coverage</h2>
        <p className="call-sub">Incoming shift offer from Sevaro Operations</p>
        <div className="call-offer">
          <strong>{call.hospital_names.join(", ")}</strong>
          <span>{clockTime(call.start)} to {clockTime(call.end)} ET</span>
          {call.expires_at && now !== null && !done && <p className="call-deadline">Reply within {countdown(call.expires_at, now)}</p>}
        </div>
        {answered && !done && call.message && <p className="call-message">{call.message}</p>}
        <p className="call-note">Synthetic demonstration · no patient details</p>
        {done ? (
          <div className="call-result">
            <p role="status">{done}</p>
            <button onClick={close}>Close</button>
          </div>
        ) : !answered ? (
          <div className="call-actions">
            <button onClick={close} className="call-btn decline">Decline</button>
            <button onClick={answer} className="call-btn answer">Answer</button>
          </div>
        ) : (
          <div className="call-replies">
            <button onClick={() => reply("accept")} className="accept">Accept shift</button>
            <button onClick={() => reply("decline")} className="decline-shift">Decline shift</button>
            <button onClick={close} className="hang-up">Hang up · reply later from Offers</button>
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
