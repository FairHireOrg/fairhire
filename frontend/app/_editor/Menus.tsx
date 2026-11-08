"use client";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import { CaretDown, Plus } from "@phosphor-icons/react";
import { KIND_LABEL } from "../_lib/doc";
import type { SectionKind } from "../_lib/types";

/** Close on outside press or Escape, returning focus to the trigger on Escape. */
function useDismiss(open: boolean, close: () => void, root: React.RefObject<HTMLElement | null>) {
  useEffect(() => {
    if (!open) return;
    const down = (e: PointerEvent) => { if (!root.current?.contains(e.target as Node)) close(); };
    const key = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      close();
      root.current?.querySelector<HTMLElement>("[data-trigger]")?.focus();
    };
    document.addEventListener("pointerdown", down);
    document.addEventListener("keydown", key);
    return () => { document.removeEventListener("pointerdown", down); document.removeEventListener("keydown", key); };
  }, [open, close, root]);
}

/** Arrow keys move between items; the first item takes focus when the menu opens. */
function useMenuKeys(open: boolean, menu: React.RefObject<HTMLElement | null>) {
  useEffect(() => {
    if (open) menu.current?.querySelector<HTMLElement>("[role=menuitem]:not([disabled])")?.focus();
  }, [open, menu]);
  return (e: React.KeyboardEvent) => {
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    const items = [...(menu.current?.querySelectorAll<HTMLElement>("[role=menuitem]:not([disabled])") ?? [])];
    if (!items.length) return;
    e.preventDefault();
    const at = items.indexOf(document.activeElement as HTMLElement);
    const next = e.key === "ArrowDown" ? (at + 1) % items.length : (at - 1 + items.length) % items.length;
    items[next].focus();
  };
}

/* ------------------------------------------------------------------ export */

export type ExportKind = "docx" | "pdf" | "txt";
const EXPORTS: { kind: ExportKind; tag: string; title: string; desc: string }[] = [
  { kind: "docx", tag: "DOCX", title: "Word document (.docx)", desc: "Editable in Word and Google Docs" },
  { kind: "pdf", tag: "PDF", title: "PDF (print)", desc: "Opens your print dialog, text-based" },
  { kind: "txt", tag: "TXT", title: "Plain text (.txt)", desc: "Exactly what a parser extracts" },
];

export function ExportMenu({ busy, onExport }: { busy: ExportKind | null; onExport: (k: ExportKind) => void }) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const menu = useRef<HTMLDivElement>(null);
  const id = useId();
  const close = useCallback(() => setOpen(false), []);
  useDismiss(open, close, root);
  const keys = useMenuKeys(open, menu);
  return (
    <div className="menu-wrap" ref={root}>
      <button
        type="button" data-trigger className="btn btn-primary btn-sm" disabled={!!busy}
        aria-haspopup="menu" aria-expanded={open} aria-controls={open ? id : undefined}
        onClick={() => setOpen(o => !o)}
      >
        {busy ? "Preparing…" : <>Export <CaretDown size={12} weight="bold" /></>}
      </button>
      {open && (
        <div className="menu menu-export" id={id} role="menu" aria-label="Export" ref={menu} onKeyDown={keys}>
          {EXPORTS.map(x => (
            <button key={x.kind} type="button" role="menuitem" className="menu-item" onClick={() => { close(); onExport(x.kind); }}>
              <span className="menu-tag mono" aria-hidden="true">{x.tag}</span>
              <span className="menu-text"><strong>{x.title}</strong><span>{x.desc}</span></span>
            </button>
          ))}
          <div className="menu-sep" role="separator" />
          <p className="menu-note">Real text only. No images or text boxes.</p>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ add section */

const ADDABLE: SectionKind[] = ["experience", "education", "projects", "skills", "publications", "certifications", "awards", "custom"];

export function AddSectionMenu({ onAdd }: { onAdd: (k: SectionKind) => void }) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const menu = useRef<HTMLDivElement>(null);
  const id = useId();
  const close = useCallback(() => setOpen(false), []);
  useDismiss(open, close, root);
  const keys = useMenuKeys(open, menu);
  return (
    <div className="menu-wrap" ref={root}>
      <button
        type="button" data-trigger className="btn btn-sm btn-quiet"
        aria-haspopup="menu" aria-expanded={open} aria-controls={open ? id : undefined}
        onClick={() => setOpen(o => !o)}
      >
        <Plus size={13} weight="bold" /> Add section
      </button>
      {open && (
        <div className="menu menu-add" id={id} role="menu" aria-label="Add a section" ref={menu} onKeyDown={keys}>
          {ADDABLE.map((k, i) => (
            <WithSeparator key={k} sep={i === ADDABLE.length - 1}>
              <button type="button" role="menuitem" className="menu-item menu-item-plain" onClick={() => { close(); onAdd(k); }}>
                <Plus size={13} weight="bold" className="menu-plus" aria-hidden="true" /> {KIND_LABEL[k]}
              </button>
            </WithSeparator>
          ))}
        </div>
      )}
    </div>
  );
}

function WithSeparator({ sep, children }: { sep: boolean; children: React.ReactNode }) {
  return <>{sep && <div className="menu-sep" role="separator" />}{children}</>;
}

/* ------------------------------------------------------------------ start over */

export function ResetConfirm({ onConfirm }: { onConfirm: () => void }) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const id = useId();
  const close = useCallback(() => setOpen(false), []);
  useDismiss(open, close, root);
  return (
    <div className="menu-wrap" ref={root}>
      <button
        type="button" data-trigger className="btn btn-sm btn-quiet"
        aria-haspopup="dialog" aria-expanded={open} aria-controls={open ? id : undefined}
        onClick={() => setOpen(o => !o)}
      >
        Start over
      </button>
      {open && (
        <div className="menu menu-confirm" id={id} role="alertdialog" aria-labelledby={`${id}-t`} aria-describedby={`${id}-d`}>
          <h2 id={`${id}-t`}>Replace this resume?</h2>
          <p id={`${id}-d`}>Your draft is saved only in this browser. Starting over clears it and can’t be undone.</p>
          <div className="menu-actions">
            <button type="button" className="btn btn-sm btn-quiet" autoFocus onClick={close}>Cancel</button>
            <button type="button" className="btn btn-sm btn-danger" onClick={() => { close(); onConfirm(); }}>Replace resume</button>
          </div>
        </div>
      )}
    </div>
  );
}
