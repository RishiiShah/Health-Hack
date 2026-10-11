// The live trace: an ECG-style line that sweeps while the clock runs and lies flat when it is paused.
import "./ui.css";

const BEAT = "M0 12 H14 L17 9 L20 12 H24 L26 3 L29 21 L32 12 H38 L42 8 L46 12 H60";
const FLAT = "M0 12 H60";

export function Pulse({ live = true, label }: { live?: boolean; label?: string }) {
  return <span className={`pulse ${live ? "is-live" : "is-flat"}`} role={label ? "img" : undefined} aria-label={label} aria-hidden={label ? undefined : true}>
    <svg viewBox="0 0 60 24" preserveAspectRatio="none" focusable="false">
      <path className="pulse-ghost" d={live ? BEAT : FLAT} />
      <path className="pulse-line" d={live ? BEAT : FLAT} pathLength={1} />
    </svg>
  </span>;
}
