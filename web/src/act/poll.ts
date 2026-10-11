// One request at a time. Cleanup invalidates the in-flight result and cancels the next poll.
export function startPolling<T>(load: (signal: AbortSignal) => Promise<T>, receive: (value: T) => void,
  fail: (error: unknown) => void, intervalMs: number): () => void {
  let active = true;
  let timer: ReturnType<typeof setTimeout> | undefined;
  const controller = new AbortController();
  async function poll() {
    try {
      const value = await load(controller.signal);
      if (active) receive(value);
    } catch (error) {
      if (active) fail(error);
    } finally {
      if (active && intervalMs > 0) timer = setTimeout(poll, intervalMs);
    }
  }
  void poll();
  return () => { active = false; controller.abort(); clearTimeout(timer); };
}
