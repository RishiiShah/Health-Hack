import { readSession } from "../auth/session.ts";
import { useAudio } from "./useAudio.ts";

export function OfferAudio({ path }: { path: string }) {
  const role = readSession()?.user.role;
  const permitted = role === "lead" || role === "physician";
  const audio = useAudio(permitted ? path : null);
  if (!permitted) return null;
  return <>
    <button className="btn" onClick={audio.active ? audio.stop : audio.play}>{audio.active ? "Stop audio" : "Play offer"}</button>
    {audio.error && <p className="error" role="alert">{audio.error}</p>}
  </>;
}
