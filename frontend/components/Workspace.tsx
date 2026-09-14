"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { ArrowRight, ArrowUpRight, CheckCircle, DownloadSimple, FileText, Files, Info, ListChecks, MagnifyingGlass, PencilLine, Plus, Question, ShieldCheck, Trash, UploadSimple, X } from "@phosphor-icons/react";
import { analyzeFitness, exportDocument, putDocument, type AtsDimension, type AtsRecommendation, type EducationItem, type ExperienceItem, type FitnessResult, type KeywordGroup, type ResumeDocument } from "@/lib/api";
import Onboarding from "./Onboarding";

const SAMPLE_JD = `Backend Engineer
Requirements
- Proficiency in Python and SQL.
- Experience with REST APIs and Docker.
- Strong communication skills.
Preferred
- Experience with Kubernetes.
- Familiarity with Kafka.
Benefits
Flexible working hours and paid leave.`;
const SAMPLE_RESUME = `Morgan Rivera
morgan.rivera@example.com
San Francisco, CA

Summary
Backend engineer building reliable services for small businesses.

Skills
Python, PostgreSQL, REST APIs, Docker, Git

Experience
Backend Engineer | Harbor Software | 2022 - 2026
- Built Python services that reduced processing time by 32%.
- Designed REST APIs for a customer reporting platform.
- Documented API integrations for engineering and customer support teams.
- Deployed Docker containers with automated health checks.

Education
Bachelor's degree in Computer Science
River Valley University | 2018 - 2022`;

type Mode = "upload" | "paste";
type Snapshot = { jd: string; resume: string; file: File | null; mode: Mode };

function DimBar({ d }: { d: AtsDimension }) {
  const pct = Math.max(0, Math.min(100, d.score));
  return (
    <div>
      <div className="dim-row">
        <span>{d.label}</span>
        <strong className="mono">{Math.round(d.score)} / 100</strong>
      </div>
      <div className="dim-track" aria-hidden="true"><span style={{ width: pct + "%" }} /></div>
      {d.detail ? <p className="dim-detail">{d.detail}</p> : null}
    </div>
  );
}

function Field({ label, value }: { label: string; value: string | string[] | null | undefined }) {
  if (!value || (Array.isArray(value) && value.length === 0)) return null;
  return (
    <div>
      <dt>{label}</dt>
      <dd>{Array.isArray(value) ? value.join(" · ") : value}</dd>
    </div>
  );
}

function EditorField({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (v: string) => void; placeholder?: string }) {
  return (
    <label className="field">
      <span>{label}</span>
      <input value={value} placeholder={placeholder} onChange={e => onChange(e.target.value)} />
    </label>
  );
}

function EditorArea({ label, value, onChange, rows, placeholder }: { label: string; value: string; onChange: (v: string) => void; rows?: number; placeholder?: string }) {
  return (
    <label className="field">
      <span>{label}</span>
      <textarea className="editor-textarea" rows={rows ?? 3} value={value} placeholder={placeholder} onChange={e => onChange(e.target.value)} />
    </label>
  );
}

function KeywordRow({ g }: { g: KeywordGroup }) {  return (
    <li className="requirement-row">
      <span className={g.matched ? "status-icon success-text" : "status-icon muted"}>
        {g.matched ? <CheckCircle size={21} weight="fill" /> : <MagnifyingGlass size={21} />}
      </span>
      <span className="requirement-text">
        <strong>{g.term}</strong>
        <span>{g.matched ? `Found: ${g.resume_term}` : "Not found in the resume"}</span>
      </span>
      <span className={"badge " + (g.matched ? "success" : "neutral")}>
        {g.kind}
      </span>
    </li>
  );
}

export default function Workspace() {
  const [jd, setJD] = useState("");
  const [resume, setResume] = useState("");
  const [mode, setMode] = useState<Mode>("upload");
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<FitnessResult | null>(null);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [replay, setReplay] = useState(0);
  const [method, setMethod] = useState(false);
  const [doc, setDoc] = useState<ResumeDocument | null>(null);
  const [docScore, setDocScore] = useState<number | null>(null);
  const [docGrade, setDocGrade] = useState("");
  const [docRecs, setDocRecs] = useState<AtsRecommendation[]>([]);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [docError, setDocError] = useState("");
  const upload = useRef<HTMLInputElement>(null);
  const summary = useRef<HTMLElement>(null);

  const stale = !!snapshot && (snapshot.jd !== jd || snapshot.mode !== mode || (mode === "paste" ? snapshot.resume !== resume : snapshot.file !== file));

  function sample() { setJD(SAMPLE_JD); setResume(SAMPLE_RESUME); setMode("paste"); setFile(null); setError(""); }
  async function run() {
    if (mode === "upload" ? !file : !resume.trim()) { setError(mode === "upload" ? "Choose a resume file, or switch to Paste text." : "Paste your resume before analyzing."); return; }
    setLoading(true); setError("");
    const input = { jd, resume, mode, file };
    try {
      const response = await analyzeFitness({ jobDescription: jd, file: mode === "upload" ? file : null, resumeText: mode === "paste" ? resume : undefined });
      setResult(response); setSnapshot(input);
      setDoc(response.document); setDirty(false); setDocError("");
      setDocScore(response.document ? Math.round(response.ats_score) : null);
      setDocGrade(response.ats_grade);
      setDocRecs(response.recommendations);
      setTimeout(() => summary.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 60);
    } catch (e) { setError(e instanceof Error ? e.message : "Analysis failed. Please try again."); }
    finally { setLoading(false); }
  }
  function chooseFile(value: File | undefined) {
    if (!value) return;
    if (!/\.(pdf|docx|txt|md)$/i.test(value.name)) { setError("Choose a PDF, DOCX, TXT, or Markdown file."); return; }
    if (value.size > 10 * 1024 * 1024) { setError("Choose a file smaller than 10 MB."); return; }
    setFile(value); setError("");
  }
  function patchDoc(patch: Partial<ResumeDocument>) {
    setDoc(d => (d ? { ...d, ...patch } : d));
    setDirty(true);
  }
  async function saveDoc() {
    if (!doc) return;
    setSaving(true); setDocError("");
    try {
      const scored = await putDocument(doc);
      setDoc(scored.document); setDirty(false);
      setDocScore(Math.round(scored.ats_score)); setDocGrade(scored.ats_grade);
      setDocRecs(scored.recommendations);
    } catch (e) { setDocError(e instanceof Error ? e.message : "Could not re-score the document."); }
    finally { setSaving(false); }
  }
  async function downloadDocx() {
    const current = dirty && doc ? await putDocument(doc).catch(() => null) : null;
    const source = current?.document ?? doc;
    if (!source) return;
    if (current) { setDoc(current.document); setDirty(false); setDocScore(Math.round(current.ats_score)); setDocGrade(current.ats_grade); setDocRecs(current.recommendations); }
    setExporting(true); setDocError("");
    try {
      const blob = await exportDocument(source);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${(source.contact.name || "resume").trim().toLowerCase().replace(/\s+/g, "-") || "resume"}-ats.docx`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 5000);
    } catch (e) { setDocError(e instanceof Error ? e.message : "Could not export the document."); }
    finally { setExporting(false); }
  }

  const sections = result?.sections_found ?? {};
  const sectionsFound = Object.entries(sections).filter(([, v]) => v).map(([k]) => k);
  const highSeverity = result?.recommendations.filter((r) => r.severity === "high").length ?? 0;

  return <div className="app-shell">
    <a className="skip-link" href="#main">Skip to workspace</a>
    <aside className="sidebar">
      <Link className="brand" href="/"><span className="brand-icon"><Files size={23} weight="bold" /></span>FairHire</Link>
      <span className="sidebar-label">Workspace</span>
      <a className="nav-item active" href="#main"><MagnifyingGlass size={19} />Resume checker</a>
      <button className="nav-item" onClick={() => { setMethod(!method); }}><ShieldCheck size={19} />How it works</button>
      <div className="sidebar-bottom">
        <div className="sidebar-note"><ShieldCheck size={23} /><h3>Parsability first.</h3><p>We score how a reading system extracts your resume.</p></div>
        <button className="nav-item" onClick={() => setReplay(r => r + 1)}><Question size={19} />Replay tutorial</button>
        <span className="sidebar-foot">Built for a clearer next step.</span>
      </div>
    </aside>
    <div className="app-body">
      <header className="topbar"><div className="breadcrumb"><span>Workspace</span><span>/</span><strong>Resume checker</strong></div><button className="text-button" onClick={() => setReplay(r => r + 1)}><Question size={17} />Replay tutorial</button></header>
      <main id="main">
        <div className="page-heading">
          <div>
            <p className="eyebrow">Pass the automated screen</p>
            <h1>How cleanly a system reads your resume.</h1>
            <p>An ATS-parsability score from exactly what a parser can extract. Add the job description if you also want keyword relevance.</p>
          </div>
          <span className="heading-icon" aria-hidden="true"><Files size={42} weight="light" /></span>
        </div>
        {method && <section className="method-panel" id="method">
          <div className="section-heading"><h2>What this result means</h2><button className="icon-button" aria-label="Close methodology" onClick={() => setMethod(false)}><X size={19} /></button></div>
          <p>The score is computed only from the resume: contact block, standard section headings, chronological roles, an education entry, a keyword-rich skills section, and scannable bullets. Exact rules, so the same resume always scores the same.</p>
          <p>The job description is optional and never affects the score — it only surfaces which of its concepts already appear as keywords in the resume.</p>
          <p>This is not a hiring probability, a measure of ability, or evidence that a screener is unbiased. It tells you how well a machine can read the document.</p>
        </section>}
        <form onSubmit={event => { event.preventDefault(); void run(); }} noValidate>
          <div className="input-grid">
            <section className="input-panel" data-tour="jd">
              <div className="input-heading"><div><span className="step-number">1</span><label htmlFor="job-description">Job description <em className="optional">optional</em></label></div><button type="button" className="text-button" disabled={loading} onClick={sample}>Try an example<ArrowUpRight size={14} /></button></div>
              <p className="input-hint">Used only to check keyword relevance — it never changes your score.</p>
              <textarea id="job-description" maxLength={30000} disabled={loading} value={jd} onChange={e => setJD(e.target.value)} placeholder={"Paste the job description here (optional)...\n\nInclude responsibilities, required skills, and preferred qualifications."} aria-describedby="jd-count" />
              <div className="input-footer"><span>Keyword relevance only</span><span id="jd-count">{jd.length.toLocaleString()} / 30,000</span></div>
            </section>
            <section className="input-panel" data-tour="resume">
              <div className="input-heading"><div><span className="step-number">2</span><h2>Your resume</h2></div><div className="segmented" role="group" aria-label="Resume input mode"><button type="button" aria-pressed={mode === "upload"} disabled={loading} onClick={() => setMode("upload")}>Upload file</button><button type="button" aria-pressed={mode === "paste"} disabled={loading} onClick={() => setMode("paste")}>Paste text</button></div></div>
              <p className="input-hint">Use the version you plan to send with your application.</p>
              {mode === "paste" ? <textarea aria-label="Resume text" disabled={loading} maxLength={100000} value={resume} onChange={e => setResume(e.target.value)} placeholder={"Paste your resume here...\n\nInclude your experience, skills, projects, and education."} /> : <div className="upload-area" onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); if (!loading) chooseFile(e.dataTransfer.files[0]); }}><input ref={upload} type="file" aria-label="Upload resume" accept=".pdf,.docx,.txt,.md" disabled={loading} onChange={e => chooseFile(e.target.files?.[0])} className="file-input" /><span className="upload-icon">{file ? <FileText size={30} /> : <UploadSimple size={30} />}</span><h3>{file ? file.name : "Drop your resume here"}</h3><p>{file ? (file.size / 1024).toFixed(0) + " KB · Ready to analyze" : "PDF, DOCX, TXT, or Markdown. Up to 10 MB."}</p><button type="button" className="button secondary" disabled={loading} onClick={() => upload.current?.click()}>{file ? "Choose a different file" : "Browse files"}<ArrowRight size={15} /></button></div>}
              <div className="input-footer"><span>{mode === "upload" ? "Text-based PDFs work best" : "Only pasted text will be analyzed"}</span><span>{mode === "paste" ? resume.length.toLocaleString() + " characters" : "10 MB max"}</span></div>
            </section>
          </div>
          <div className="analyze-bar" data-tour="submit"><p><ShieldCheck size={18} />Document contents are not saved in your browser.</p><button className="button primary analyze-button" type="submit" disabled={loading}>{loading ? <><span className="spinner" />Checking parsability</> : <>Check parsability<ArrowRight size={18} /></>}</button>{error && <div className="error-message" role="alert"><Info size={19} /><span>{error}</span></div>}</div>
        </form>
        {loading && <section className="loading-panel" role="status" aria-live="polite"><div className="section-heading"><h2>Reading your resume like an ATS would</h2><span className="spinner" /></div><p>Locating the contact block, section headings, roles, and keywords.</p><div className="skeleton-lines"><span /><span /><span /></div></section>}
        {!result && !loading && <section className="start-state"><div className="start-icon"><ListChecks size={28} weight="light" /></div><div><h2>Your resume, as a machine reads it.</h2><p>Add your resume to get a parsability score, a breakdown of what was extracted, and steps to make it ATS-clean.</p></div><span className="empty-note">No score without evidence.</span></section>}
        {result && !loading && <div className="results">
          {stale && <div className="notice" role="status">Your documents have changed. These results reflect the previous analysis. Choose Check parsability to update them.</div>}
          <section className="results-summary" ref={summary} data-tour="summary" id="summary">
            <div className="score-panel">
              <div className="caption">ATS parsability</div>
              <div className="score-value">{Math.round(result.ats_score)}<span className="score-denom">/ 100</span></div>
              <div className="grade-badge">{result.ats_grade}</div>
              <h2>How cleanly a system reads your resume</h2>
              <p>Resume-only, rule-based scoring. Not a prediction of a hiring decision.</p>
              <button className="text-button" onClick={() => setMethod(!method)}>How is this calculated?<ArrowUpRight size={14} /></button>
            </div>
            <div className="coverage-panel">
              <h3>Parsability breakdown</h3>
              {result.dimensions.map(d => <DimBar key={d.key} d={d} />)}
            </div>
            <div className="quality-panel">
              <div className="caption">What was read</div>
              <strong className="quality-value">{sectionsFound.length}<span>/ 6 sections</span></strong>
              <h3>Contact, roles and sections detected</h3>
              <p>{sectionsFound.length ? sectionsFound.join(" · ") : "None of the standard headings were found."}</p>
              <a className="text-button" href="#keywords">See detected skills<ArrowRight size={15} /></a>
            </div>
          </section>

          <section className="qualities">
            <div className="section-heading"><div><h2>Make it ATS-clean</h2><p>Prioritized, actionable fixes. Each one is easy to read by a parser.</p></div>{result.recommendations.length > 0 && <span className="badge warning">{highSeverity} high priority</span>}</div>
            {result.recommendations.length === 0
              ? <p className="muted">No ATS blockers found. Great — keep the structure.</p>
              : <ol className="recommendation-list">{result.recommendations.map(r => <li key={r.code} className={"recommendation " + r.severity}><div><span className={"badge " + (r.severity === "high" ? "warning" : r.severity === "medium" ? "neutral" : "success")}>{r.severity}</span><h3>{r.title}</h3></div><p>{r.detail}</p><p className="action"><ArrowRight size={14} />{r.action}</p></li>)}</ol>}
          </section>

          {doc && <section className="editor-panel" id="editor">
            <div className="section-heading">
              <div>
                <h2><PencilLine size={17} /> Fix it in the editor</h2>
                <p>Edit the structured resume, re-score instantly, and export an ATS-safe DOCX when the checklist clears.</p>
              </div>
              {docRecs.length > 0
                ? <span className="badge warning">{docRecs.length} issue{docRecs.length === 1 ? "" : "s"} left</span>
                : <span className="badge success">ATS-clean</span>}
            </div>
            {docScore !== null && <p className="editor-score">Live score <strong className="mono">{docScore} / 100</strong> <span className="grade-badge">{docGrade}</span>{dirty && <span className="muted"> · unsaved changes</span>}</p>}
            {docRecs.length > 0 && <ol className="recommendation-list editor-checklist">
              {docRecs.map(r => <li key={r.code} className={"recommendation " + r.severity}>
                <div>
                  <span className={"badge " + (r.severity === "high" ? "warning" : r.severity === "medium" ? "neutral" : "success")}>{r.severity}</span>
                  <h3>{r.title}</h3>
                  {r.line >= 1 && <span className="mono muted">line {r.line}</span>}
                </div>
                <p className="action"><ArrowRight size={14} />{r.action}</p>
              </li>)}
            </ol>}
            <div className="editor-grid">
              <div className="editor-card">
                <h3>Contact</h3>
                <EditorField label="Name" value={doc.contact.name} onChange={v => patchDoc({ contact: { ...doc.contact, name: v } })} placeholder="Jordan Ellis" />
                <EditorField label="Email" value={doc.contact.email} onChange={v => patchDoc({ contact: { ...doc.contact, email: v } })} placeholder="you@example.com" />
                <EditorField label="Phone" value={doc.contact.phone} onChange={v => patchDoc({ contact: { ...doc.contact, phone: v } })} placeholder="(555) 123-4567" />
                <EditorField label="Location" value={doc.contact.location} onChange={v => patchDoc({ contact: { ...doc.contact, location: v } })} placeholder="City, ST" />
                <EditorField label="LinkedIn" value={doc.contact.linkedin} onChange={v => patchDoc({ contact: { ...doc.contact, linkedin: v } })} placeholder="linkedin.com/in/..." />
                <EditorField label="GitHub" value={doc.contact.github} onChange={v => patchDoc({ contact: { ...doc.contact, github: v } })} placeholder="github.com/..." />
              </div>
              <div className="editor-card">
                <h3>Summary</h3>
                <EditorArea label="Professional summary" rows={5} value={doc.summary} onChange={v => patchDoc({ summary: v })} placeholder="2–3 lines under a standard 'Summary' heading." />
              </div>
              <div className="editor-card">
                <h3>Skills</h3>
                <EditorArea label="Comma-separated skills" rows={4} value={doc.skills.join(", ")} onChange={v => patchDoc({ skills: v.split(/[,;\n]/).map(s => s.trim()).filter(Boolean) })} placeholder="Python, PostgreSQL, Docker" />
              </div>
              <div className="editor-card">
                <h3>Education</h3>
                {doc.education.map((e, i) => <div key={i} className="editor-item">
                  <EditorField label="Degree" value={e.degree} onChange={v => patchDoc({ education: doc.education.map((x, j) => j === i ? { ...x, degree: v } : x) })} placeholder="B.S. Computer Science" />
                  <EditorField label="School" value={e.school} onChange={v => patchDoc({ education: doc.education.map((x, j) => j === i ? { ...x, school: v } : x) })} placeholder="University" />
                  <EditorField label="Year" value={e.year} onChange={v => patchDoc({ education: doc.education.map((x, j) => j === i ? { ...x, year: v } : x) })} placeholder="2021" />
                  <button type="button" className="icon-button" aria-label="Remove education entry" onClick={() => patchDoc({ education: doc.education.filter((_, j) => j !== i) })}><Trash size={16} /></button>
                </div>)}
                <button type="button" className="button secondary" onClick={() => patchDoc({ education: [...doc.education, { degree: "", school: "", year: "" } as EducationItem] })}><Plus size={14} /> Add education</button>
              </div>
            </div>
            <div className="editor-card">
              <h3>Experience</h3>
              {doc.experience.length === 0 && <p className="muted">No roles yet — add your first one.</p>}
              {doc.experience.map((e, i) => {
                const set = (p: Partial<ExperienceItem>) => patchDoc({ experience: doc.experience.map((x, j) => j === i ? { ...x, ...p } : x) });
                return <div key={i} className="editor-item editor-role">
                  <EditorField label="Title" value={e.title} onChange={v => set({ title: v })} placeholder="Backend Engineer" />
                  <EditorField label="Company" value={e.company} onChange={v => set({ company: v })} placeholder="Company" />
                  <EditorField label="Start" value={e.start} onChange={v => set({ start: v })} placeholder="June 2021" />
                  <EditorField label="End" value={e.end} onChange={v => set({ end: v })} placeholder="March 2024" />
                  <EditorArea label="Bullets (one per line, start with action verbs)" rows={4} value={e.bullets.join("\n")} onChange={v => set({ bullets: v.split("\n").map(b => b.replace(/^\s*(?:[-*•]|\d+[.)])\s*/, "").trim()).filter(Boolean) })} placeholder={"Built Python services handling 40M+ events per day"} />
                  <button type="button" className="icon-button" aria-label="Remove role" onClick={() => patchDoc({ experience: doc.experience.filter((_, j) => j !== i) })}><Trash size={16} /></button>
                </div>;
              })}
              <button type="button" className="button secondary" onClick={() => patchDoc({ experience: [...doc.experience, { title: "", company: "", location: "", start: "", end: "", bullets: [] } as ExperienceItem] })}><Plus size={14} /> Add role</button>
            </div>
            <div className="editor-card">
              <h3>Certifications &amp; projects</h3>
              <EditorArea label="Certifications (one per line)" value={doc.certifications.join("\n")} onChange={v => patchDoc({ certifications: v.split("\n").map(s => s.trim()).filter(Boolean) })} />
              <EditorArea label="Projects (one per line)" value={doc.projects.join("\n")} onChange={v => patchDoc({ projects: v.split("\n").map(s => s.trim()).filter(Boolean) })} />
            </div>
            {docError && <div className="error-message" role="alert"><Info size={19} /><span>{docError}</span></div>}
            <div className="editor-actions">
              <button type="button" className="button secondary" disabled={saving || !dirty} onClick={() => void saveDoc()}>{saving ? <><span className="spinner" />Re-scoring</> : <><CheckCircle size={16} />Save & re-score</>}</button>
              <button type="button" className="button primary" disabled={exporting} onClick={() => void downloadDocx()}>{exporting ? <><span className="spinner" />Exporting</> : <><DownloadSimple size={16} />Download ATS-safe DOCX</>}</button>
            </div>
            <p className="muted">Re-upload the exported file to verify the score holds.</p>
          </section>}

          <section className="keywords-panel" id="keywords">            <div className="section-heading"><div><h2>What the system read</h2><p>The parsed identity, sections, and detected technologies.</p></div></div>
            <div className="profile-grid">
              <dl className="profile-fields"><Field label="Name" value={result.resume_fields.name} /><Field label="Email" value={result.resume_fields.email} /><Field label="Phone" value={result.resume_fields.phone} /><Field label="Location" value={result.resume_fields.location} /><Field label="LinkedIn" value={result.resume_fields.linkedin} /><Field label="GitHub" value={result.resume_fields.github} /><Field label="Degrees" value={result.resume_fields.degrees} /><Field label="Roles" value={result.resume_fields.titles} /><Field label="Date ranges" value={result.resume_fields.date_ranges} /></dl>
              <div><h3>Detected technologies</h3>{result.skills.length ? <div className="skill-cloud">{result.skills.map(s => <span key={s}>{s}</span>)}</div> : <p className="muted">No recognizable technologies were tagged.</p>}</div>
            </div>
          </section>

          {result.keyword_groups.length > 0 && <section className="requirements-panel">
            <div className="section-heading"><div><h2>Job keyword relevance</h2><p>Which job concepts already appear in your resume. Informational — the job description is not scored.</p></div><span className="badge neutral">{result.keyword_coverage.matched} / {result.keyword_coverage.total} present</span></div>
            <ul className="requirement-list keywords">{result.keyword_groups.map(g => <KeywordRow key={g.term + g.kind} g={g} />)}</ul>
          </section>}

          <aside className="interpretation"><Info size={22} /><h3>It&rsquo;s about read-ability.</h3><p>A low score usually means a parse issue: an image-based PDF, a layout that hides text, or a missing standard heading — not that you could not do the job.</p><details><summary>Extracted document details</summary><dl>{Object.entries(result.resume_fields).filter(([, value]) => value && (!Array.isArray(value) || value.length)).map(([key, value]) => <div key={key}><dt>{key.replaceAll("_", " ")}</dt><dd>{Array.isArray(value) ? value.join(", ") : value}</dd></div>)}</dl></details></aside>

          <p className="result-disclaimer">{result.disclaimer}</p>
        </div>}
        <footer><span>© 2026 FairHire. All rights reserved.</span><button className="text-button" onClick={() => setMethod(!method)}>About the matching process<ArrowUpRight size={14} /></button></footer>
      </main>
    </div>
    <Onboarding replay={replay} ready={!!result && !loading} />
  </div>;
}
