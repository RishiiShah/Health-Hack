// A headline number that counts to its new value when the server changes it.
import { stagger, useCountUp } from "./motion.ts";
import "./ui.css";

export type Tone = "risk" | "warn" | "good" | undefined;

export function Kpi({ label, value, of, note, href, tone, order = 0 }: { label: string; value: number; of?: number; note: string; href: string; tone?: Tone; order?: number }) {
  const shown = useCountUp(value);
  return <a className={`kpi rise ${tone ?? ""}`} href={href} style={stagger(order)}>
    <span className="kpi-label">{label}</span>
    <strong className="kpi-value">{shown}{of !== undefined && <small>/{of}</small>}</strong>
    <span className="kpi-note">{note}<i aria-hidden="true">→</i></span>
  </a>;
}

export function Chip({ label, value, href, order = 0 }: { label: string; value: number; href: string; order?: number }) {
  const shown = useCountUp(value);
  return <a className={`chip rise ${value ? "warn" : ""}`} href={href} style={stagger(order)}>{label}<b>{shown}</b></a>;
}
