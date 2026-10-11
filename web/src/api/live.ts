// Serialized polling: a reset or clock change must not be overwritten by an older request.
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./client.ts";
import { startPolling, type Polling } from "../act/poll.ts";

export type Snapshot = {
  revision: number;
  epoch: string;
  clock: { mode: string; now: string };
  [section: string]: unknown;
};

export type Live = { snapshot: Snapshot | null; receivedAt: number; error: string | null; refresh: () => void };

export function useSnapshot(intervalMs = 2000): Live {
  const [state, setState] = useState<Omit<Live, "refresh">>({ snapshot: null, receivedAt: 0, error: null });

  const polling = useRef<Polling | null>(null);
  const refresh = useCallback(() => polling.current?.refresh(), []);

  useEffect(() => {
    const stop = startPolling((signal) => api<Snapshot>("/snapshot", { signal }),
      (snapshot) => setState({ snapshot, receivedAt: Date.now(), error: null }),
      (error) => setState((prev) => ({ ...prev, error: error instanceof Error ? error.message : "Snapshot refresh failed." })), intervalMs);
    polling.current = stop;
    return () => { stop(); polling.current = null; };
  }, [intervalMs]);

  return { ...state, refresh };
}
