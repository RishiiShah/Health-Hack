import { apiBlob } from "./client.ts";

// Media elements cannot attach bearer headers. Fetch privately, then play a temporary local URL.
export function createAudioPlayer(status: (active: boolean) => void, fail: (message: string) => void) {
  let generation = 0;
  let controller: AbortController | null = null;
  let audio: HTMLAudioElement | null = null;
  let objectUrl: string | null = null;

  function stop() {
    generation++;
    controller?.abort();
    controller = null;
    if (audio) {
      audio.pause();
      audio.removeAttribute("src");
      audio.load();
      audio = null;
    }
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    objectUrl = null;
    status(false);
  }

  async function play(path: string) {
    stop();
    const current = generation;
    controller = new AbortController();
    status(true);
    try {
      if (typeof Audio === "undefined") throw new Error("This browser cannot play audio.");
      const blob = await apiBlob(path, { signal: controller.signal });
      if (generation !== current) return;
      objectUrl = URL.createObjectURL(blob);
      audio = new Audio(objectUrl);
      audio.addEventListener("ended", () => { if (generation === current) stop(); }, { once: true });
      audio.addEventListener("error", () => {
        if (generation === current) { stop(); fail("Audio could not be played. Try again."); }
      }, { once: true });
      await audio.play();
    } catch (error) {
      if (generation !== current) return;
      stop();
      fail(error instanceof Error && error.name === "NotAllowedError"
        ? "Your browser blocked playback. Press Play to try again."
        : error instanceof Error ? error.message : "Audio could not be played. Try again.");
    }
  }

  return { play, stop };
}
