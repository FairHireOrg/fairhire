"use client";
import { useLayoutEffect, useRef, useState } from "react";

/**
 * Inline fields for the page view.
 *
 * They are real <input>/<textarea> elements (so IME, paste, autofill and screen readers just work)
 * styled to disappear into the typeset page. Widths follow their content via a hidden sizer.
 */

export function InlineText({ value, onChange, placeholder, label, className = "", inputMode, autoFocus, flag, title, align, onEnter }: {
  value: string; onChange: (v: string) => void; placeholder: string; label: string; className?: string;
  inputMode?: "text" | "email" | "tel" | "url"; autoFocus?: boolean; flag?: boolean; title?: string;
  align?: "right"; onEnter?: () => void;
}) {
  return (
    <span className={`ix ${flag ? "is-flag" : ""} ${align === "right" ? "ix-right" : ""} ${className}`} data-v={value || placeholder || " "} title={title}>
      <input
        size={1} value={value} placeholder={placeholder} aria-label={label} inputMode={inputMode} autoFocus={autoFocus}
        spellCheck={inputMode ? false : undefined}
        onChange={e => onChange(e.target.value)}
        onKeyDown={e => { if (e.key === "Enter" && onEnter && !e.nativeEvent.isComposing) { e.preventDefault(); onEnter(); } }}
      />
    </span>
  );
}

/** Wrapping text that grows with its content. Enter/Backspace hooks let bullets behave like a list. */
export function InlineArea({ value, onChange, placeholder, label, className = "", onEnter, onBackspaceEmpty, onFocus, onBlur, innerRef }: {
  value: string; onChange: (v: string) => void; placeholder: string; label: string; className?: string;
  onEnter?: () => void; onBackspaceEmpty?: () => void; onFocus?: () => void; onBlur?: () => void;
  innerRef?: (el: HTMLTextAreaElement | null) => void;
}) {
  const ref = useRef<HTMLTextAreaElement | null>(null);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "0px";
    el.style.height = `${el.scrollHeight}px`;
  }, [value]);
  // The page scales with its width, so re-measure when it does.
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    let w = el.clientWidth;
    const ro = new ResizeObserver(() => {
      if (el.clientWidth === w) return;
      w = el.clientWidth;
      el.style.height = "0px";
      el.style.height = `${el.scrollHeight}px`;
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return (
    <textarea
      ref={el => { ref.current = el; innerRef?.(el); }}
      className={`ia ${className}`} rows={1} value={value} placeholder={placeholder} aria-label={label}
      onFocus={onFocus} onBlur={onBlur}
      onChange={e => onChange(e.target.value.replace(/\n/g, " "))}
      onKeyDown={e => {
        if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing && onEnter) { e.preventDefault(); onEnter(); }
        if (e.key === "Backspace" && value === "" && onBackspaceEmpty) { e.preventDefault(); onBackspaceEmpty(); }
      }}
    />
  );
}

/** Comma separated list that keeps what you typed while you type, and parses on every change. */
export function CommaList({ items, onChange, placeholder, label, className = "" }: {
  items: string[]; onChange: (v: string[]) => void; placeholder: string; label: string; className?: string;
}) {
  const [draft, setDraft] = useState<string | null>(null);
  const value = draft ?? items.join(", ");
  return (
    <InlineArea
      className={className} label={label} placeholder={placeholder} value={value}
      onFocus={() => setDraft(items.join(", "))}
      onBlur={() => setDraft(null)}
      onChange={v => {
        setDraft(v);
        onChange(v.split(/[,;]/).map(s => s.trim()).filter(Boolean));
      }}
    />
  );
}
