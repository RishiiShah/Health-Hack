// One request at a time. Cleanup invalidates the in-flight result and cancels the next poll.
export type Polling = (() => void) & { refresh: () => void };

export function startPolling<T>(load: (signal: AbortSignal) => Promise<T>, receive: (value: T) => void,
  fail: (error: unknown) => void, intervalMs: number): Polling {
  let active = true;
  let running = false;
  let requested = false;
  let timer: ReturnType<typeof setTimeout> | undefined;
  const controller = new AbortController();
  async function poll() {
    running = true;
    requested = false;
    try {
      const value = await load(controller.signal);
      if (active && !requested) receive(value);
    } catch (error) {
      if (active && !requested) fail(error);
    } finally {
      running = false;
      if (active && requested) void poll();
      else if (active && intervalMs > 0) timer = setTimeout(poll, intervalMs);
    }
  }
  void poll();
  return Object.assign(() => { active = false; controller.abort(); clearTimeout(timer); }, {
    refresh: () => {
      if (!active) return;
      clearTimeout(timer);
      if (running) requested = true;
      else void poll();
    },
  });
}
