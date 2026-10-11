// A modal on the native <dialog>: focus is trapped, Esc closes it, and the page behind stays put.
import { useEffect, useRef, type ReactNode } from "react";

export function Modal({ open, title, kicker, onClose, children }: {
  open: boolean; title: string; kicker?: string; onClose: () => void; children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);
  return (
    <dialog ref={ref} className="modal" aria-label={title} data-lenis-prevent onClose={onClose}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      {open && <div className="modal-body">
        <header className="modal-head">
          <div>{kicker && <span className="kicker">{kicker}</span>}<h2>{title}</h2></div>
          <button className="icon-btn" aria-label="Close" onClick={onClose}>
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18" /></svg>
          </button>
        </header>
        {children}
      </div>}
    </dialog>
  );
}
