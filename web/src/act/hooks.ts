import { useEffect, useState } from "react";
import { ApiError, api } from "../api/client.ts";
import { STATIC_OFFERS, type Snapshot } from "../api/live.ts";
import { serverNow } from "./time.ts";

export type Loaded<T> = { data: T | null; error: ApiError | null };

// GETs `path` again whenever `reloadKey` changes; keeps the last data while a reload fails.
export function useApi<T>(path: string | null, reloadKey?: unknown): Loaded<T> {
  const [state, setState] = useState<Loaded<T>>({ data: null, error: null });
  useEffect(() => {
    if (!path) return;
    let current = true;
    api<T>(path).catch((error: unknown) => {
      if (path === "/offers") return STATIC_OFFERS as T;
      throw error;
    }).then(
      (data) => current && setState({ data, error: null }),
      (error: ApiError) => current && setState((prev) => ({ data: prev.data, error })),
    );
    return () => { current = false; };
  }, [path, reloadKey]);
  return state;
}

// FastAPI answers an unknown route with 404 "Not Found"; other errors carry the server's own detail.
export function unavailableText(error: ApiError, route: string): string {
  return error.status === 404 && error.message === "Not Found" ? `Not available yet: the server doesn't serve ${route}.` : error.message;
}

export function useServerNow(snapshot: Snapshot | null, receivedAt: number): number | null {
  const [tick, setTick] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setTick(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  return snapshot ? serverNow(snapshot.clock.now, snapshot.clock.mode, receivedAt, tick) : null;
}
