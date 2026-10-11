import { useState } from "react";
import { useAudio } from "../api/useAudio.ts";

// Plays the server's audio for the selected critical item after the user's gesture.
export function VoiceAlerts({ itemId }: { itemId: string | null }) {
  const [enabled, setEnabled] = useState(false);
  const [muted, setMuted] = useState(false);
  const audio = useAudio(itemId ? `/alerts/${encodeURIComponent(itemId)}/audio` : null);
  return <section className="panel voice-panel">
    <div><h2>Voice alerts</h2><p className="muted">Play the selected critical item's announcement.</p></div>
    <div className="voice-actions">
      <button className="btn primary" onClick={() => setEnabled(true)}>{enabled ? "Voice alerts enabled" : "Enable voice alerts"}</button>
      <button className="btn" aria-pressed={muted} onClick={() => { audio.stop(); setMuted(!muted); }}>{muted ? "Unmute" : "Mute"}</button>
      <button className="btn" onClick={audio.active ? audio.stop : audio.play} disabled={!enabled || muted || !itemId}>{audio.active ? "Stop audio" : "Play critical"}</button>
    </div>
    {audio.error && <p className="error" role="alert">{audio.error}</p>}
  </section>;
}
