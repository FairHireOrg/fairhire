"use client";
import { Fragment, useEffect, useRef, useState } from "react";
import { ArrowDown, ArrowUp, Plus, Trash, X } from "@phosphor-icons/react";
import { ENTRY_LABELS, KIND_LABEL, dateLooksSafe, newEntry } from "../_lib/doc";
import type { Contact, Entry, ResumeDoc, Section, Severity, SkillGroup } from "../_lib/types";
import { CommaList, InlineArea, InlineText } from "./Inline";

export type Update = (fn: (d: ResumeDoc) => ResumeDoc) => void;
/** Worst severity per section or entry id, taken from the checks. Drives the margin marks on the page. */
export type Issues = Record<string, Severity>;

const move = <T,>(list: T[], from: number, to: number): T[] => {
  if (to < 0 || to >= list.length) return list;
  const next = [...list];
  next.splice(to, 0, next.splice(from, 1)[0]);
  return next;
};

function Tools({ label, index, count, onMove, onDelete }: {
  label: string; index: number; count: number; onMove: (to: number) => void; onDelete: () => void;
}) {
  return (
    <span className="pg-tools" role="group" aria-label={`${label} actions`}>
      <button type="button" className="pg-tool" aria-label={`Move ${label} up`} disabled={index === 0} onClick={() => onMove(index - 1)}><ArrowUp size={13} weight="bold" /></button>
      <button type="button" className="pg-tool" aria-label={`Move ${label} down`} disabled={index === count - 1} onClick={() => onMove(index + 1)}><ArrowDown size={13} weight="bold" /></button>
      <button type="button" className="pg-tool pg-tool-del" aria-label={`Delete ${label}`} onClick={onDelete}><Trash size={13} weight="bold" /></button>
    </span>
  );
}

/* ------------------------------------------------------------------ header */

function Header({ contact, onChange, issue }: { contact: Contact; onChange: (c: Contact) => void; issue?: Severity }) {
  const set = <K extends keyof Contact>(k: K, v: Contact[K]) => onChange({ ...contact, [k]: v });
  const [focusLink, setFocusLink] = useState<number | null>(null);
  return (
    <header className="pg-head" data-section="contact" data-issue={issue}>
      <InlineText className="pg-name" label="Full name" placeholder="Your name" value={contact.name} onChange={v => set("name", v)} />
      <InlineText className="pg-headline" label="Headline" placeholder="Headline, e.g. Backend Engineer" value={contact.headline} onChange={v => set("headline", v)} />
      <p className="pg-contact">
        <InlineText label="Email" placeholder="email@example.com" inputMode="email" value={contact.email} onChange={v => set("email", v)} />
        <i aria-hidden="true">|</i>
        <InlineText label="Phone" placeholder="Phone" inputMode="tel" value={contact.phone} onChange={v => set("phone", v)} />
        <i aria-hidden="true">|</i>
        <InlineText label="Location" placeholder="City, State" value={contact.location} onChange={v => set("location", v)} />
        {contact.links.map((l, i) => (
          <Fragment key={i}>
            <i aria-hidden="true">|</i>
            <span className="pg-link">
              <InlineText
                label={`Link ${i + 1}`} placeholder="linkedin.com/in/you" inputMode="url" value={l} autoFocus={focusLink === i}
                onChange={v => set("links", contact.links.map((x, j) => (j === i ? v : x)))}
              />
              <button type="button" className="pg-x" aria-label={`Remove link ${i + 1}`} onClick={() => set("links", contact.links.filter((_, j) => j !== i))}><X size={10} weight="bold" /></button>
            </span>
          </Fragment>
        ))}
        <button type="button" className="pg-ghost" onClick={() => { set("links", [...contact.links, ""]); setFocusLink(contact.links.length); }}>
          <Plus size={11} weight="bold" /> Link
        </button>
      </p>
      {contact.other.length > 0 && (
        <div className="pg-other" role="group" aria-label="Lines we could not place">
          <p>These lines at the top didn’t match a contact field. Keep what belongs and remove the rest.</p>
          {contact.other.map((o, i) => (
            <span className="pg-other-row" key={i}>
              <InlineText label={`Unplaced line ${i + 1}`} placeholder="Line" value={o} onChange={v => set("other", contact.other.map((x, j) => (j === i ? v : x)))} />
              <button type="button" className="pg-x" aria-label={`Remove unplaced line ${i + 1}`} onClick={() => set("other", contact.other.filter((_, j) => j !== i))}><X size={10} weight="bold" /></button>
            </span>
          ))}
        </div>
      )}
    </header>
  );
}

/* ------------------------------------------------------------------ entries */

function Bullets({ bullets, onChange }: { bullets: string[]; onChange: (b: string[]) => void }) {
  const refs = useRef<(HTMLTextAreaElement | null)[]>([]);
  // Which bullet should take focus after the next render (a new or neighbouring one).
  const focusNext = useRef<number | null>(null);
  useEffect(() => {
    if (focusNext.current === null) return;
    refs.current[focusNext.current]?.focus();
    focusNext.current = null;
  });
  const set = (i: number, v: string) => onChange(bullets.map((b, j) => (j === i ? v : b)));
  return (
    <ul className="pg-bullets">
      {bullets.map((b, i) => (
        <li key={i}>
          <span className="pg-dot" aria-hidden="true">•</span>
          <InlineArea
            label={`Bullet ${i + 1}`} placeholder="Start with a verb: Built, Reduced, Led…" value={b}
            innerRef={el => { refs.current[i] = el; }}
            onChange={v => set(i, v)}
            onEnter={() => { focusNext.current = i + 1; onChange([...bullets.slice(0, i + 1), "", ...bullets.slice(i + 1)]); }}
            onBackspaceEmpty={() => {
              if (bullets.length === 1) return;
              focusNext.current = Math.max(0, i - 1);
              onChange(bullets.filter((_, j) => j !== i));
            }}
          />
          <button type="button" className="pg-x pg-x-row" aria-label={`Delete bullet ${i + 1}`}
            onClick={() => onChange(bullets.length === 1 ? [""] : bullets.filter((_, j) => j !== i))}><X size={10} weight="bold" /></button>
        </li>
      ))}
    </ul>
  );
}

function EntryBlock({ kind, entry, index, count, issue, onChange, onMove, onDelete }: {
  kind: Section["kind"]; entry: Entry; index: number; count: number; issue?: Severity;
  onChange: (e: Entry) => void; onMove: (to: number) => void; onDelete: () => void;
}) {
  const L = ENTRY_LABELS[kind];
  const set = <K extends keyof Entry>(k: K, v: Entry[K]) => onChange({ ...entry, [k]: v });
  const [extra, setExtra] = useState({ detail: !!entry.detail, link: !!entry.link });
  const unsafe = (v: string) => !dateLooksSafe(v);
  const dateTip = "Use Month YYYY, for example Jun 2024";
  const what = KIND_LABEL[kind].toLowerCase();
  return (
    <article className="pg-entry" data-entry={entry.id} data-issue={issue}>
      <Tools label={`${what} entry`} index={index} count={count} onMove={onMove} onDelete={onDelete} />
      <div className="pg-row">
        <InlineText className="pg-title" label={L.heading} placeholder={L.heading} value={entry.heading} onChange={v => set("heading", v)} />
        <span className="pg-dates">
          <InlineText label="Start date" placeholder="Start" value={entry.start} flag={unsafe(entry.start)} title={unsafe(entry.start) ? dateTip : undefined} onChange={v => set("start", v)} />
          <span aria-hidden="true">–</span>
          <InlineText label="End date" placeholder="End" value={entry.end} flag={unsafe(entry.end)} title={unsafe(entry.end) ? dateTip : undefined} onChange={v => set("end", v)} />
        </span>
      </div>
      <div className="pg-row pg-sub">
        <InlineText label={L.subheading} placeholder={L.subheading} value={entry.subheading} onChange={v => set("subheading", v)} />
        <span className="pg-ghosts">
          {!extra.detail && <button type="button" className="pg-ghost" onClick={() => setExtra(x => ({ ...x, detail: true }))}><Plus size={11} weight="bold" /> {kind === "education" ? "GPA or honors" : "Detail"}</button>}
          {!extra.link && <button type="button" className="pg-ghost" onClick={() => setExtra(x => ({ ...x, link: true }))}><Plus size={11} weight="bold" /> Link</button>}
        </span>
        <InlineText align="right" label="Location" placeholder="Location" value={entry.location} onChange={v => set("location", v)} />
      </div>
      {(extra.detail || entry.detail) && (
        <div className="pg-row pg-sub">
          <InlineText autoFocus={extra.detail && !entry.detail} label={L.detail} placeholder={L.detail} value={entry.detail} onChange={v => set("detail", v)} />
        </div>
      )}
      {(extra.link || entry.link) && (
        <div className="pg-row pg-sub">
          <InlineText autoFocus={extra.link && !entry.link} label="Link" placeholder="example.com/project" inputMode="url" value={entry.link} onChange={v => set("link", v)} />
        </div>
      )}
      <Bullets bullets={entry.bullets.length ? entry.bullets : [""]} onChange={b => set("bullets", b)} />
    </article>
  );
}

/* ------------------------------------------------------------------ skills */

function Skills({ groups, onChange }: { groups: SkillGroup[]; onChange: (g: SkillGroup[]) => void }) {
  const list = groups.length ? groups : [{ label: "", items: [] }];
  const set = (i: number, g: SkillGroup) => onChange(list.map((x, j) => (j === i ? g : x)));
  return (
    <div className="pg-skills">
      {list.map((g, i) => (
        <div className="pg-skill" key={i}>
          <span className="pg-skill-label">
            <InlineText label="Skill group name" placeholder="Group" value={g.label} onChange={v => set(i, { ...g, label: v })} />
            <span aria-hidden="true">:</span>
          </span>
          <CommaList label={`Skills in ${g.label || `group ${i + 1}`}`} placeholder="Python, SQL, Docker…" items={g.items} onChange={items => set(i, { ...g, items })} />
          <button type="button" className="pg-x pg-x-row" aria-label={`Delete skill group ${g.label || i + 1}`} onClick={() => onChange(list.filter((_, j) => j !== i))}><X size={10} weight="bold" /></button>
        </div>
      ))}
      <button type="button" className="pg-ghost pg-add" onClick={() => onChange([...list, { label: "", items: [] }])}><Plus size={11} weight="bold" /> Add group</button>
    </div>
  );
}

/* ------------------------------------------------------------------ page */

export function ResumePage({ doc, update, issues = {} }: { doc: ResumeDoc; update: Update; issues?: Issues }) {
  const setSection = (id: string, s: Section) => update(d => ({ ...d, sections: d.sections.map(x => (x.id === id ? s : x)) }));
  return (
    <div className="pg-wrap">
      <article className="pg" aria-label="Resume">
        <Header contact={doc.contact} issue={issues.contact} onChange={contact => update(d => ({ ...d, contact }))} />

        <section className="pg-sec" data-section="summary" data-issue={issues.summary}>
          <h2 className="pg-h">Summary</h2>
          <InlineArea
            className="pg-para" label="Summary" value={doc.summary}
            placeholder="Two or three sentences: who you are, what you do, one concrete strength."
            onChange={summary => update(d => ({ ...d, summary }))}
          />
        </section>

        {doc.sections.map((s, i) => {
          const std = KIND_LABEL[s.kind];
          return (
            <section className="pg-sec" key={s.id} data-section={s.id} data-issue={issues[s.id]} aria-label={std}>
              <Tools
                label={std} index={i} count={doc.sections.length}
                onMove={to => update(d => ({ ...d, sections: move(d.sections, i, to) }))}
                onDelete={() => update(d => ({ ...d, sections: d.sections.filter(x => x.id !== s.id) }))}
              />
              <h2 className="pg-h">
                {s.kind === "custom"
                  ? <InlineText label="Section title" placeholder="Section title" value={s.title} onChange={title => setSection(s.id, { ...s, title })} />
                  : std}
              </h2>
              {s.kind === "skills" ? (
                <Skills groups={s.groups} onChange={groups => setSection(s.id, { ...s, groups })} />
              ) : (
                <>
                  {s.entries.map((e, j) => (
                    <EntryBlock
                      key={e.id} kind={s.kind} entry={e} index={j} count={s.entries.length} issue={issues[e.id]}
                      onChange={next => setSection(s.id, { ...s, entries: s.entries.map(x => (x.id === e.id ? next : x)) })}
                      onMove={to => setSection(s.id, { ...s, entries: move(s.entries, j, to) })}
                      onDelete={() => setSection(s.id, { ...s, entries: s.entries.filter(x => x.id !== e.id) })}
                    />
                  ))}
                  <button type="button" className="pg-ghost pg-add" onClick={() => setSection(s.id, { ...s, entries: [...s.entries, newEntry()] })}>
                    <Plus size={11} weight="bold" /> Add {s.kind === "experience" ? "a role" : "an entry"}
                  </button>
                </>
              )}
            </section>
          );
        })}

        {!doc.sections.length && (
          <p className="pg-empty">Use <strong>Add section</strong> above to add experience, education, skills and more.</p>
        )}
      </article>
    </div>
  );
}
