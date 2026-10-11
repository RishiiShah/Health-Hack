import { useEffect, useMemo, useState } from "react";
import { createAudioPlayer } from "./audio.ts";

export function useAudio(path: string | null) {
  const [active, setActive] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const player = useMemo(() => createAudioPlayer(setActive, setError), []);
  useEffect(() => {
    setError(null);
    return () => player.stop();
  }, [player, path]);
  return { active, error, stop: player.stop,
    play: () => { if (path) { setError(null); void player.play(path); } } };
}
