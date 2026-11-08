"use client";
import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { X } from "@phosphor-icons/react";

export function Field({ label, hint, warn, children, className = "" }: {
  label: string; hint?: string; warn?: string; children: (id: string) => React.ReactNode; className?: string;
}) {
  const id = useId();
  return (
    <div className={`field ${className}`}>
      <label htmlFor={id}>{label}</label>
      {children(id)}
      {warn ? <p className="field-warn">{warn}</p> : hint ? <p className="field-hint">{hint}</p> : null}
    </div>
  );
}

export function TextInput({ id, value, onChange, placeholder, inputMode, autoComplete }: {
  id?: string; value: string; onChange: (v: string) => void; placeholder?: string;
  inputMode?: "text" | "email" | "tel" | "url"; autoComplete?: string;
}) {
  return (
    <input id={id} className="input" value={value} placeholder={placeholder} inputMode={inputMode}
      autoComplete={autoComplete} spellCheck={inputMode ? false : undefined} onChange={e => onChange(e.target.value)} />
  );
}

/** Textarea that grows with its content; Enter/Backspace hooks let bullet lists behave like a list. */
export const AutoText = function AutoText({ id, value, onChange, placeholder, onEnter, onBackspaceEmpty, innerRef, rows = 1, label }: {
  id?: string; value: string; onChange: (v: string) => void; placeholder?: string;
  onEnter?: () => void; onBackspaceEmpty?: () => void;
  innerRef?: (el: HTMLTextAreaElement | null) => void; rows?: number; label?: string;
}) {
  const ref = useRef<HTMLTextAreaElement | null>(null);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [value]);
  return (
    <textarea
      id={id} ref={el => { ref.current = el; innerRef?.(el); }} className="input input-auto" rows={rows} value={value}
      placeholder={placeholder} aria-label={label}
      onChange={e => onChange(e.target.value.replace(/\n/g, " "))}
      onKeyDown={e => {
        if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing && onEnter) { e.preventDefault(); onEnter(); }
        if (e.key === "Backspace" && value === "" && onBackspaceEmpty) { e.preventDefault(); onBackspaceEmpty(); }
      }}
    />
  );
};

/** Tag input: Enter / comma / paste-a-list adds, Backspace on empty removes the last chip. */
export function ChipInput({ items, onChange, placeholder, label }: {
  items: string[]; onChange: (v: string[]) => void; placeholder?: string; label: string;
}) {
  const [draft, setDraft] = useState("");
  const add = (raw: string) => {
    const parts = raw.split(/[,;\n]/).map(s => s.trim()).filter(Boolean);
    if (!parts.length) return;
    const seen = new Set(items.map(i => i.toLowerCase()));
    const next = [...items];
    for (const p of parts) if (!seen.has(p.toLowerCase())) { seen.add(p.toLowerCase()); next.push(p); }
    onChange(next);
    setDraft("");
  };
  return (
    <div className="chips" onClick={e => (e.currentTarget.querySelector("input") as HTMLInputElement | null)?.focus()}>
      {items.map((it, i) => (
        <span className="chip" key={`${it}-${i}`}>
          {it}
          <button type="button" aria-label={`Remove ${it}`} onClick={() => onChange(items.filter((_, j) => j !== i))}><X size={11} weight="bold" /></button>
        </span>
      ))}
      <input
        className="chip-input" value={draft} aria-label={label}
        placeholder={items.length ? "" : placeholder} onChange={e => {
          const v = e.target.value;
          if (/[,;]$/.test(v)) add(v); else setDraft(v);
        }}
        onKeyDown={e => {
          if (e.key === "Enter") { e.preventDefault(); add(draft); }
          else if (e.key === "Backspace" && !draft && items.length) onChange(items.slice(0, -1));
        }}
        onBlur={() => add(draft)}
        onPaste={e => {
          const t = e.clipboardData.getData("text");
          if (/[,;\n]/.test(t)) { e.preventDefault(); add(draft + t); }
        }}
      />
    </div>
  );
}

/** Focus a form target referenced by the checks panel. */
export function useJump(): (target: { section: string; entry: string }) => void {
  return (t) => {
    const sel = t.entry ? `[data-entry="${t.entry}"]` : `[data-section="${t.section}"]`;
    const el = document.querySelector<HTMLElement>(sel) ?? document.querySelector<HTMLElement>(`[data-section="${t.section}"]`);
    if (!el) return;
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    el.classList.remove("flash");
    void el.offsetWidth;
    el.classList.add("flash");
    el.querySelector<HTMLElement>("input, textarea")?.focus({ preventScroll: true });
  };
}

export function useOnce(fn: () => void) {
  useEffect(fn, []); // eslint-disable-line react-hooks/exhaustive-deps
}
