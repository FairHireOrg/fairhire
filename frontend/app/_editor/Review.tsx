"use client";
import { useMemo, useState } from "react";
import { CheckCircle, Warning, WarningOctagon } from "@phosphor-icons/react";
import type { Ats, Recommendation, ResumeDoc, Scored, Severity, Target } from "../_lib/types";

const SEV_LABEL: Record<Severity, string> = { high: "Blocks parsing", medium: "Likely to misread", low: "Polish" };
const SEV_ICON = { high: WarningOctagon, medium: Warning, low: Warning } as const;
const GRADE_TONE: Record<string, string> = { Strong: "ok", Good: "ok", "Needs work": "warn", "Likely missed": "bad" };

const GRADE_COPY: Record<string, string> = {
  Strong: "A parser should read this cleanly.",
  Good: "Mostly readable, with a few things worth fixing.",
  "Needs work": "Parts of this may be misread or skipped.",
  "Likely missed": "A parser will probably struggle to read this.",
};

/* ------------------------------------------------------------------ checks */

export function ChecksPanel({ scored, original, scoring, onJump }: {
  scored: Scored | null; original: Ats | null; scoring: boolean; onJump: (t: Target) => void;
}) {
  const [showBreakdown, setShowBreakdown] = useState(false);
  if (!scored) {
    return <div className="review-empty">{scoring ? "Reading your resume…" : "Add some content and the checks will appear here."}</div>;
  }
  const { ats } = scored;
  const tone = GRADE_TONE[ats.grade] ?? "warn";
  const delta = original ? Math.round(ats.score - original.score) : 0;
  const recs = ats.recommendations;
  return (
    <div className={`checks ${scoring ? "is-stale" : ""}`} aria-busy={scoring}>
      <div className={`readiness tone-${tone}`}>
        <div className="readiness-top">
          <div>
            <p className="eyebrow">Parser readability</p>
            <p className="readiness-grade display">{ats.grade}</p>
          </div>
          <p className="readiness-score mono" aria-label={`Score ${Math.round(ats.score)} out of 100`}>
            {Math.round(ats.score)}<span>/100</span>
          </p>
        </div>
        <div className="meter" role="presentation"><span style={{ width: `${Math.max(2, ats.score)}%` }} /></div>
        <p className="readiness-copy">{GRADE_COPY[ats.grade] ?? ""}</p>
        {original && (
          <p className="readiness-delta">
            As uploaded: <strong>{Math.round(original.score)}</strong>
            {delta !== 0 && <span className={delta > 0 ? "up" : "down"}> ({delta > 0 ? "+" : ""}{delta})</span>}
          </p>
        )}
      </div>

      <p className="fine-print">
        This describes how reliably software can read the document. It is not a judgement of you or your experience,
        and the same resume always gets the same result.
      </p>

      <h3 className="panel-h">{recs.length ? `${recs.length} thing${recs.length === 1 ? "" : "s"} to fix` : "Nothing to fix"}</h3>
      {recs.length === 0 && (
        <p className="all-clear"><CheckCircle size={18} weight="fill" /> No parsing problems found in this document.</p>
      )}
      <ul className="recs">
        {recs.map((r, i) => <Rec key={`${r.code}-${i}`} rec={r} onJump={onJump} />)}
      </ul>

      <button type="button" className="link-btn" aria-expanded={showBreakdown} onClick={() => setShowBreakdown(!showBreakdown)}>
        {showBreakdown ? "Hide" : "Show"} breakdown
      </button>
      {showBreakdown && (
        <ul className="dims">
          {ats.dimensions.map(d => (
            <li key={d.key}>
              <div className="dim-row"><span>{d.label}</span><span className="mono">{Math.round(d.score)}</span></div>
              <div className="meter meter-sm"><span style={{ width: `${Math.max(2, d.score)}%` }} /></div>
              <p>{d.detail}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Rec({ rec, onJump }: { rec: Recommendation; onJump: (t: Target) => void }) {
  const Icon = SEV_ICON[rec.severity];
  const canJump = !!rec.target.section && !rec.target.section.startsWith("new:");
  return (
    <li className={`rec sev-${rec.severity}`}>
      <button type="button" disabled={!canJump} onClick={() => onJump(rec.target)} aria-label={`${rec.title}. ${canJump ? "Go to the problem" : ""}`}>
        <Icon size={18} weight="fill" className="rec-icon" />
        <span className="rec-body">
          <span className="rec-sev">{SEV_LABEL[rec.severity]}</span>
          <span className="rec-title">{rec.title}</span>
          <span className="rec-detail">{rec.detail}</span>
          <span className="rec-action">{rec.action}</span>
        </span>
      </button>
    </li>
  );
}

/* ------------------------------------------------------------------ parser view */

export function ParserView({ scored, originalText, onJump }: {
  scored: Scored | null; originalText: string; onJump: (t: Target) => void;
}) {
  const [which, setWhich] = useState<"after" | "before">("after");
  const flagged = useMemo(() => {
    const m = new Map<number, Severity>();
    for (const r of scored?.ats.recommendations ?? []) if (r.line >= 0) m.set(r.line, m.get(r.line) ?? r.severity);
    return m;
  }, [scored]);
  const text = which === "after" ? scored?.text ?? "" : originalText;
  const lines = text.replace(/\n$/, "").split("\n");
  return (
    <div className="parser">
      <p className="fine-print">
        This is the plain text a tracking system extracts from your export — one column, in reading order.
        {originalText ? " Compare it with what was read from your original file." : ""}
      </p>
      {originalText && (
        <div className="seg" role="tablist" aria-label="Which text to show">
          <button role="tab" aria-selected={which === "after"} onClick={() => setWhich("after")}>After cleanup</button>
          <button role="tab" aria-selected={which === "before"} onClick={() => setWhich("before")}>As uploaded</button>
        </div>
      )}
      <ol className="lines mono" aria-label="Extracted text">
        {lines.map((ln, i) => {
          const sev = which === "after" ? flagged.get(i) : undefined;
          const owner = which === "after" ? scored?.owners[i] : undefined;
          const clickable = !!owner?.section;
          return (
            <li key={i} className={sev ? `flag sev-${sev}` : ""}>
              <button type="button" tabIndex={clickable ? 0 : -1} disabled={!clickable} onClick={() => owner && onJump(owner)}>
                <span className="ln">{i + 1}</span>
                <span className="lt">{ln || " "}</span>
              </button>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

/* ------------------------------------------------------------------ preview */

const dateRange = (s: string, e: string) => [s, e].filter(Boolean).join(" – ");

export function Preview({ doc }: { doc: ResumeDoc }) {
  const c = doc.contact;
  const contactLine = [c.email, c.phone, c.location, ...c.links].filter(Boolean).join("  |  ");
  return (
    <div className="sheet-wrap">
      <article className="sheet" aria-label="Resume preview">
        {c.name && <h1 className="sheet-name">{c.name}</h1>}
        {c.headline && <p className="sheet-headline">{c.headline}</p>}
        {contactLine && <p className="sheet-contact">{contactLine}</p>}
        {doc.summary && (<><h2>Summary</h2><p>{doc.summary}</p></>)}
        {doc.sections.map(s => {
          const title = s.kind === "custom" ? s.title : ({
            experience: "Work Experience", education: "Education", projects: "Projects", skills: "Skills",
            publications: "Publications", certifications: "Certifications", awards: "Awards", custom: s.title,
          })[s.kind];
          if (s.kind === "skills") {
            if (!s.groups.some(g => g.items.length)) return null;
            return (
              <div key={s.id}>
                <h2>{title}</h2>
                {s.groups.map((g, i) => <p key={i}>{g.label && <strong>{g.label}: </strong>}{g.items.join(", ")}</p>)}
              </div>
            );
          }
          if (!s.entries.length) return null;
          return (
            <div key={s.id}>
              <h2>{title}</h2>
              {s.entries.map(e => (
                <div className="sheet-entry" key={e.id}>
                  <p className="sheet-row">
                    <strong>{[e.heading, e.subheading].filter(Boolean).join(", ")}</strong>
                    <span>{[e.location, dateRange(e.start, e.end)].filter(Boolean).join("  ·  ")}</span>
                  </p>
                  {(e.detail || e.link) && <p className="sheet-sub">{[e.detail, e.link].filter(Boolean).join("  ·  ")}</p>}
                  {e.bullets.some(b => b.trim()) && <ul>{e.bullets.filter(b => b.trim()).map((b, i) => <li key={i}>{b}</li>)}</ul>}
                </div>
              ))}
            </div>
          );
        })}
      </article>
    </div>
  );
}
