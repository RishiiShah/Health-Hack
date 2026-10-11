// Light and dark themes. The choice is remembered on this device; until one is made, the system setting decides.
// Switching spreads the new theme as a circle from the toggle (View Transitions); without support, or with
// reduced motion, it switches at once.
import { useEffect, useState, type MouseEvent } from "react";
import { flushSync } from "react-dom";
import { prefersReducedMotion } from "./motion.ts";
import "./ui.css";

export type Theme = "light" | "dark";
const KEY = "overlap-theme";
const CHANGED = "overlap-theme-changed";

function stored(): Theme | null {
  try {
    const value = localStorage.getItem(KEY);
    return value === "light" || value === "dark" ? value : null;
  } catch {
    return null;
  }
}
const system = (): Theme => (globalThis.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light");
const current = (): Theme => stored() ?? system();

// Every toggle on the page shares one theme, kept in sync through a document event.
export function useTheme(): Theme {
  const [theme, setTheme] = useState<Theme>(current);
  useEffect(() => {
    const sync = () => setTheme(current());
    const query = globalThis.matchMedia?.("(prefers-color-scheme: dark)");
    query?.addEventListener("change", sync);
    addEventListener(CHANGED, sync);
    return () => { query?.removeEventListener("change", sync); removeEventListener(CHANGED, sync); };
  }, []);
  useEffect(() => { document.documentElement.dataset.theme = theme; }, [theme]);
  return theme;
}

function apply(next: Theme) {
  try { localStorage.setItem(KEY, next); } catch { /* not remembered; still applies now */ }
  document.documentElement.dataset.theme = next;
  dispatchEvent(new Event(CHANGED));
}

export function ThemeToggle() {
  const theme = useTheme();
  const next: Theme = theme === "dark" ? "light" : "dark";
  const toggle = (event: MouseEvent<HTMLButtonElement>) => {
    const doc = document as Document & { startViewTransition?: (update: () => void) => { ready: Promise<void> } };
    if (!doc.startViewTransition || prefersReducedMotion()) { apply(next); return; }
    const box = event.currentTarget.getBoundingClientRect();
    const root = document.documentElement.style;
    root.setProperty("--reveal-x", `${((box.left + box.width / 2) / innerWidth) * 100}vw`);
    root.setProperty("--reveal-y", `${((box.top + box.height / 2) / innerHeight) * 100}vh`);
    doc.startViewTransition(() => flushSync(() => apply(next)));
  };
  return <button type="button" className="icon-btn theme-toggle" onClick={toggle} aria-label={`Switch to ${next} mode`} title={`Switch to ${next} mode`}>
    {theme === "dark"
      ? <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4.5" /><path d="M12 2.5v2.2M12 19.3v2.2M2.5 12h2.2M19.3 12h2.2M5.3 5.3l1.6 1.6M17.1 17.1l1.6 1.6M5.3 18.7l1.6-1.6M17.1 6.9l1.6-1.6" /></svg>
      : <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z" /></svg>}
  </button>;
}

export const Brand = ({ tag = true }: { tag?: boolean }) =>
  <span className="brand"><span className="brand-mark" aria-hidden="true"><i /><i /></span><strong>Cerevia</strong>{tag && <em>for Sevaro</em>}</span>;
