// Motion helpers. Everything here steps aside when the person asks for reduced motion.
import { useEffect, useRef, useState, type CSSProperties } from "react";

export const prefersReducedMotion = () => globalThis.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;

// Counts from the last shown value to the new one with an ease-out, so a changed number is noticed.
export function useCountUp(target: number, durationMs = 700): number {
  // First paint counts up from zero; later changes count from the value on screen.
  const [shown, setShown] = useState(() => (prefersReducedMotion() ? target : 0));
  const from = useRef(shown);
  useEffect(() => {
    const start = from.current;
    if (start === target || prefersReducedMotion()) {
      from.current = target;
      setShown(target);
      return;
    }
    const began = performance.now();
    let frame = 0;
    const step = (now: number) => {
      const t = Math.min(1, (now - began) / durationMs);
      const eased = 1 - (1 - t) ** 3;
      const value = Math.round(start + (target - start) * eased);
      from.current = value;
      setShown(value);
      if (t < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [target, durationMs]);
  return shown;
}

// Stagger index for entrance animations: style={stagger(i)} sets --i, which motion.css multiplies by its step.
export const stagger = (i: number) => ({ "--i": Math.min(i, 12) }) as CSSProperties;
