// Page building blocks: heading, numbered section and panel. Pages compose these instead of repeating markup.
import type { ReactNode } from "react";
import { stagger } from "./motion.ts";
import "./ui.css";

export function PageHead({ kicker, title, note, children }: { kicker?: string; title: string; note?: ReactNode; children?: ReactNode }) {
  return <header className="page-head rise">
    <div className="page-head-text">{kicker && <span className="kicker">{kicker}</span>}<h1>{title}</h1>{note && <p>{note}</p>}</div>
    {children && <div className="page-head-aside">{children}</div>}
  </header>;
}

export function Section({ id, index, kicker, title, note, aside, children }: {
  id?: string; index?: number; kicker?: string; title: string; note?: ReactNode; aside?: ReactNode; children: ReactNode;
}) {
  const headingId = id ? `${id}-heading` : undefined;
  return <section id={id} className="section" aria-labelledby={headingId}>
    <div className="section-head rise">
      <div>
        {(index !== undefined || kicker) && <span className="kicker">{index !== undefined && <b>{String(index).padStart(2, "0")}</b>}{kicker}</span>}
        <h2 id={headingId}>{title}</h2>
        {note && <p>{note}</p>}
      </div>
      {aside && <div className="section-aside">{aside}</div>}
    </div>
    {children}
  </section>;
}

export function Panel({ title, note, actions, className = "", order = 0, children }: {
  title?: ReactNode; note?: ReactNode; actions?: ReactNode; className?: string; order?: number; children: ReactNode;
}) {
  return <section className={`panel rise ${className}`} style={stagger(order)}>
    {(title || actions) && <div className="panel-head"><div>{title && <h2>{title}</h2>}{note && <p className="panel-note">{note}</p>}</div>{actions}</div>}
    {children}
  </section>;
}

// A folded panel for detail that is useful but not needed at a glance.
export function Fold({ summary, children, order = 0 }: { summary: ReactNode; children: ReactNode; order?: number }) {
  return <details className="panel fold rise" style={stagger(order)}><summary>{summary}</summary><div className="fold-body">{children}</div></details>;
}

export const Empty = ({ children }: { children: ReactNode }) => <p className="empty-state">{children}</p>;
