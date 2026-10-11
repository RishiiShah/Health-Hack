// Minimal scaffold for Anish to replace with the /ws client: polls /snapshot until the WebSocket exists.
import { useCallback, useEffect, useState } from "react";
import { api } from "./client.ts";

export type Snapshot = {
  revision: number;
  epoch: string;
  clock: { mode: string; now: string };
  [section: string]: unknown;
};

export type Live = { snapshot: Snapshot | null; receivedAt: number; error: string | null; refresh: () => void };

export function useSnapshot(intervalMs = 2000): Live {
  const [state, setState] = useState<Omit<Live, "refresh">>({ snapshot: null, receivedAt: 0, error: null });

  const refresh = useCallback(() => {
    api<Snapshot>("/snapshot").then(
      (snapshot) => setState({ snapshot, receivedAt: Date.now(), error: null }),
      (error: Error) => setState((prev) => ({ ...prev, error: error.message })),
    );
  }, []);

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, intervalMs);
    return () => clearInterval(timer);
  }, [refresh, intervalMs]);

  return { ...state, refresh };
}
