"use client";
import { useEffect, useRef, useState } from "react";
import { ArrowDown, ArrowUp, CaretDown, CaretRight, Plus, Trash } from "@phosphor-icons/react";
import { AutoText, ChipInput, Field, TextInput } from "./Fields";
import { ENTRY_LABELS, KIND_LABEL, dateLooksSafe, newEntry } from "../_lib/doc";
import type { Contact, Entry, Section, SkillGroup } from "../_lib/types";

const move = <T,>(list: T[], from: number, to: number): T[] => {
  if (to < 0 || to >= list.length) return list;
  const next = [...list];
  next.splice(to, 0, next.splice(from, 1)[0]);
  return next;
};

/* ------------------------------------------------------------------ contact */

export function ContactForm({ value, onChange }: { value: Contact; onChange: (c: Contact) => void }) {
  const set = <K extends keyof Contact>(k: K, v: Contact[K]) => onChange({ ...value, [k]: v });
  return (
    <section className="card" data-section="contact" aria-labelledby="h-contact">
      <header className="card-head"><h2 id="h-contact" className="card-title">Contact</h2></header>
      <div className="grid-2">
        <Field label="Full name" className="span-2">{id => <TextInput id={id} value={value.name} onChange={v => set("name", v)} autoComplete="name" />}</Field>
        <Field label="Headline" hint="Optional — a title like “Backend Engineer”" className="span-2">
          {id => <TextInput id={id} value={value.headline} onChange={v => set("headline", v)} />}
        </Field>
        <Field label="Email">{id => <TextInput id={id} value={value.email} inputMode="email" autoComplete="email" onChange={v => set("email", v)} />}</Field>
        <Field label="Phone">{id => <TextInput id={id} value={value.phone} inputMode="tel" autoComplete="tel" onChange={v => set("phone", v)} />}</Field>
        <Field label="Location" hint="City, State">{id => <TextInput id={id} value={value.location} onChange={v => set("location", v)} />}</Field>
        <Field label="Links" hint="LinkedIn, GitHub, portfolio — press Enter after each">
          {() => <ChipInput label="Links" items={value.links} onChange={v => set("links", v)} placeholder="linkedin.com/in/you" />}
        </Field>
        {value.other.length > 0 && (
          <Field label="Other lines found at the top" hint="These didn’t match a contact field. Keep what belongs; remove the rest." className="span-2">
            {() => <ChipInput label="Other lines" items={value.other} onChange={v => set("other", v)} />}
          </Field>
        )}
      </div>
    </section>
  );
}

export function SummaryForm({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <section className="card" data-section="summary" aria-labelledby="h-summary">
      <header className="card-head"><h2 id="h-summary" className="card-title">Summary</h2></header>
      <Field label="Two or three sentences" hint="Who you are, what you do, one concrete strength.">
        {id => <AutoText id={id} rows={3} value={value} onChange={onChange} />}
      </Field>
    </section>
  );
}

/* ------------------------------------------------------------------ entries */

function BulletList({ bullets, onChange }: { bullets: string[]; onChange: (b: string[]) => void }) {
  const refs = useRef<(HTMLTextAreaElement | null)[]>([]);
  const [focusIdx, setFocusIdx] = useState<number | null>(null);
  useEffect(() => {
    if (focusIdx === null) return;
    refs.current[focusIdx]?.focus();
    setFocusIdx(null);
  }, [focusIdx, bullets.length]);

  const set = (i: number, v: string) => onChange(bullets.map((b, j) => (j === i ? v : b)));
  return (
    <div className="bullets">
      <span className="field-label">Bullets</span>
      <ul>
        {bullets.map((b, i) => (
          <li key={i}>
            <span className="bullet-dot" aria-hidden="true" />
            <AutoText
              label={`Bullet ${i + 1}`} value={b} placeholder="Start with a verb: Built, Reduced, Led…"
              innerRef={el => { refs.current[i] = el; }}
              onChange={v => set(i, v)}
              onEnter={() => { onChange([...bullets.slice(0, i + 1), "", ...bullets.slice(i + 1)]); setFocusIdx(i + 1); }}
              onBackspaceEmpty={() => {
                if (bullets.length === 1) return;
                onChange(bullets.filter((_, j) => j !== i));
                setFocusIdx(Math.max(0, i - 1));
              }}
            />
            <span className="row-actions">
              <button type="button" className="icon-btn" aria-label={`Move bullet ${i + 1} up`} disabled={i === 0} onClick={() => onChange(move(bullets, i, i - 1))}><ArrowUp size={14} /></button>
              <button type="button" className="icon-btn" aria-label={`Move bullet ${i + 1} down`} disabled={i === bullets.length - 1} onClick={() => onChange(move(bullets, i, i + 1))}><ArrowDown size={14} /></button>
              <button type="button" className="icon-btn" aria-label={`Delete bullet ${i + 1}`} onClick={() => onChange(bullets.length === 1 ? [""] : bullets.filter((_, j) => j !== i))}><Trash size={14} /></button>
            </span>
          </li>
        ))}
      </ul>
      <button type="button" className="btn btn-quiet btn-sm" onClick={() => { onChange([...bullets, ""]); setFocusIdx(bullets.length); }}>
        <Plus size={14} weight="bold" /> Add bullet
      </button>
    </div>
  );
}

function EntryCard({ kind, entry, index, count, onChange, onMove, onDelete }: {
  kind: Section["kind"]; entry: Entry; index: number; count: number;
  onChange: (e: Entry) => void; onMove: (to: number) => void; onDelete: () => void;
}) {
  const [open, setOpen] = useState(true);
  const L = ENTRY_LABELS[kind];
  const set = <K extends keyof Entry>(k: K, v: Entry[K]) => onChange({ ...entry, [k]: v });
  const title = [entry.heading, entry.subheading].filter(Boolean).join(" · ") || `Untitled ${KIND_LABEL[kind].toLowerCase()} entry`;
  const bad = (v: string) => (dateLooksSafe(v) ? undefined : "Use Month YYYY, e.g. Jun 2024");
  const showLink = kind === "projects" || kind === "publications" || kind === "custom" || !!entry.link;
  return (
    <article className="entry" data-entry={entry.id}>
      <header className="entry-head">
        <button type="button" className="entry-toggle" aria-expanded={open} onClick={() => setOpen(!open)}>
          {open ? <CaretDown size={14} weight="bold" /> : <CaretRight size={14} weight="bold" />}
          <span className="entry-title">{title}</span>
        </button>
        <span className="row-actions always">
          <button type="button" className="icon-btn" aria-label="Move entry up" disabled={index === 0} onClick={() => onMove(index - 1)}><ArrowUp size={15} /></button>
          <button type="button" className="icon-btn" aria-label="Move entry down" disabled={index === count - 1} onClick={() => onMove(index + 1)}><ArrowDown size={15} /></button>
          <button type="button" className="icon-btn" aria-label="Delete entry" onClick={onDelete}><Trash size={15} /></button>
        </span>
      </header>
      {open && (
        <div className="entry-body">
          <div className="grid-2">
            <Field label={L.heading} className="span-2">{id => <TextInput id={id} value={entry.heading} onChange={v => set("heading", v)} />}</Field>
            <Field label={L.subheading}>{id => <TextInput id={id} value={entry.subheading} onChange={v => set("subheading", v)} />}</Field>
            <Field label="Location">{id => <TextInput id={id} value={entry.location} onChange={v => set("location", v)} />}</Field>
            <Field label="Start" warn={bad(entry.start)}>{id => <TextInput id={id} value={entry.start} placeholder="Jun 2022" onChange={v => set("start", v)} />}</Field>
            <Field label={kind === "education" ? "End or expected" : "End"} warn={bad(entry.end)}>
              {id => <TextInput id={id} value={entry.end} placeholder="Present" onChange={v => set("end", v)} />}
            </Field>
            {showLink && <Field label="Link" className="span-2">{id => <TextInput id={id} value={entry.link} inputMode="url" onChange={v => set("link", v)} />}</Field>}
            <Field label={L.detail} className="span-2">{id => <TextInput id={id} value={entry.detail} onChange={v => set("detail", v)} />}</Field>
          </div>
          <BulletList bullets={entry.bullets.length ? entry.bullets : [""]} onChange={b => set("bullets", b)} />
        </div>
      )}
    </article>
  );
}

/* ------------------------------------------------------------------ skills */

function SkillsEditor({ groups, onChange }: { groups: SkillGroup[]; onChange: (g: SkillGroup[]) => void }) {
  const list = groups.length ? groups : [{ label: "", items: [] }];
  const set = (i: number, g: SkillGroup) => onChange(list.map((x, j) => (j === i ? g : x)));
  return (
    <div className="skills">
      {list.map((g, i) => (
        <div className="skill-group" key={i}>
          <div className="skill-label">
            <Field label="Group" hint={i === 0 ? "e.g. Languages" : undefined}>
              {id => <TextInput id={id} value={g.label} onChange={v => set(i, { ...g, label: v })} />}
            </Field>
          </div>
          <Field label="Skills" hint={i === 0 ? "Press Enter or comma after each. Paste a list to split it." : undefined} className="skill-items">
            {() => <ChipInput label={`Skills in group ${g.label || i + 1}`} items={g.items} onChange={items => set(i, { ...g, items })} placeholder="Python, SQL, Docker…" />}
          </Field>
          <button type="button" className="icon-btn skill-del" aria-label="Delete skill group" onClick={() => onChange(list.filter((_, j) => j !== i))}><Trash size={15} /></button>
        </div>
      ))}
      <button type="button" className="btn btn-quiet btn-sm" onClick={() => onChange([...list, { label: "", items: [] }])}>
        <Plus size={14} weight="bold" /> Add group
      </button>
    </div>
  );
}

/* ------------------------------------------------------------------ section */

export function SectionCard({ section, index, count, original, onChange, onMove, onDelete }: {
  section: Section; index: number; count: number; original?: string;
  onChange: (s: Section) => void; onMove: (to: number) => void; onDelete: () => void;
}) {
  const std = KIND_LABEL[section.kind];
  const renamed = original && original.trim().toLowerCase() !== std.toLowerCase() && section.kind !== "custom";
  return (
    <section className="card" data-section={section.id} aria-label={std}>
      <header className="card-head">
        {section.kind === "custom"
          ? <input className="input card-title-input" aria-label="Section title" value={section.title} onChange={e => onChange({ ...section, title: e.target.value })} />
          : <h2 className="card-title">{std}</h2>}
        <span className="row-actions always">
          <button type="button" className="icon-btn" aria-label={`Move ${std} up`} disabled={index === 0} onClick={() => onMove(index - 1)}><ArrowUp size={15} /></button>
          <button type="button" className="icon-btn" aria-label={`Move ${std} down`} disabled={index === count - 1} onClick={() => onMove(index + 1)}><ArrowDown size={15} /></button>
          <button type="button" className="icon-btn" aria-label={`Delete ${std}`} onClick={onDelete}><Trash size={15} /></button>
        </span>
      </header>
      {renamed && <p className="note">Your file called this “{original}”. It exports as “{std}”, the label parsers look for.</p>}
      {section.kind === "skills" ? (
        <SkillsEditor groups={section.groups} onChange={groups => onChange({ ...section, groups })} />
      ) : (
        <>
          <div className="entries">
            {section.entries.map((e, i) => (
              <EntryCard
                key={e.id} kind={section.kind} entry={e} index={i} count={section.entries.length}
                onChange={next => onChange({ ...section, entries: section.entries.map(x => (x.id === e.id ? next : x)) })}
                onMove={to => onChange({ ...section, entries: move(section.entries, i, to) })}
                onDelete={() => onChange({ ...section, entries: section.entries.filter(x => x.id !== e.id) })}
              />
            ))}
          </div>
          <button type="button" className="btn btn-sm add-entry" onClick={() => onChange({ ...section, entries: [...section.entries, newEntry()] })}>
            <Plus size={14} weight="bold" /> Add {section.kind === "experience" ? "a role" : "an entry"}
          </button>
        </>
      )}
    </section>
  );
}
