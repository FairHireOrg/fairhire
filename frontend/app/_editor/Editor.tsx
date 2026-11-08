"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowArcLeft, ArrowArcRight, CheckCircle, WarningCircle } from "@phosphor-icons/react";
import { exportDocument } from "../_lib/api";
import { newSection } from "../_lib/doc";
import { takeFile } from "../_lib/handoff";
import type { SectionKind, Severity } from "../_lib/types";
import { useResume } from "../_lib/useResume";
import { ThemeToggle } from "../_shared/ThemeToggle";
import { Wordmark } from "../_shared/Wordmark";
import { useJump } from "./Fields";
import { ImportScreen } from "./ImportScreen";
import { AddSectionMenu, ExportMenu, ResetConfirm, type ExportKind } from "./Menus";
import { ResumePage, type Issues } from "./Page";
import { ChecksPanel, ParserView, Preview } from "./Review";

type Tab = "checks" | "parser";
type Pane = "edit" | "review";
const RANK: Record<Severity, number> = { high: 3, medium: 2, low: 1 };

export default function Editor() {
  const r = useResume();
  const jump = useJump();
  const [tab, setTab] = useState<Tab>("checks");
  const [pane, setPane] = useState<Pane>("edit");
  const [busy, setBusy] = useState<ExportKind | null>(null);
  const [toast, setToast] = useState("");
  const scroller = useRef<HTMLDivElement>(null);

  // With no saved draft, open what the landing page asked for instead of the import screen:
  // a file dropped there, or a blank page for /editor?new=1.
  const router = useRouter();
  const startBlankRequested = useSearchParams().has("new");
  const { status, startBlank, fromFile } = r;
  useEffect(() => {
    if (status === "loading") return;
    const file = takeFile();
    if (status === "empty") {
      if (file) fromFile(file);
      else if (startBlankRequested) startBlank();
    }
    // Drop the one-shot flag so "Start over" later lands on the import screen.
    if (startBlankRequested) router.replace("/editor");
  }, [status, startBlankRequested, startBlank, fromFile, router]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(""), 3800);
    return () => clearTimeout(t);
  }, [toast]);

  const issues: Issues = useMemo(() => {
    const out: Issues = {};
    for (const rec of r.scored?.ats.recommendations ?? []) {
      const key = rec.target.entry || rec.target.section;
      if (!key || key.startsWith("new:")) continue;
      if (!out[key] || RANK[rec.severity] > RANK[out[key]]) out[key] = rec.severity;
    }
    return out;
  }, [r.scored]);

  if (r.status === "loading") return <div className="boot" aria-busy="true" />;
  if (r.status === "empty" || r.status === "importing") {
    return <ImportScreen busy={r.status === "importing"} error={r.error} onFile={r.fromFile} onText={r.fromText} onBlank={r.startBlank} />;
  }

  const { doc, update } = r;
  const addSection = (kind: SectionKind) => {
    const s = newSection(kind);
    update(d => ({ ...d, sections: [...d.sections, s] }));
    setPane("edit");
    setTimeout(() => jump({ section: s.id, entry: "" }), 60);
  };

  const onExport = async (kind: ExportKind) => {
    if (kind === "pdf") { window.print(); return; }
    setBusy(kind);
    try {
      const blob = await exportDocument(doc, kind);
      const name = `${(doc.contact.name || "resume").trim().toLowerCase().replace(/\s+/g, "-")}.${kind}`;
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = name;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 4000);
      setToast(`${name} downloaded`);
    } catch (e) {
      r.setError(e instanceof Error ? e.message : "Export failed.");
    } finally { setBusy(null); }
  };

  const issueCount = r.scored?.ats.recommendations.length ?? 0;
  const multiCol = r.meta.notes.includes("multi_column");
  const toJump = (t: { section: string; entry: string }) => { setPane("edit"); setTimeout(() => jump(t), 30); };

  return (
    <div className="ed" data-pane={pane}>
      <header className="ed-bar">
        <Wordmark href="/" labelClassName="bar-brand" />
        <span className="bar-file" title={r.meta.filename}>{r.meta.filename || "Untitled resume"}</span>
        <span className="bar-status" role="status" aria-live="polite">{r.scoring ? "Checking…" : "Saved in this browser"}</span>
        <span className="bar-spacer" />
        <ThemeToggle />
        <ExportMenu busy={busy} onExport={onExport} />
        <ResetConfirm onConfirm={r.reset} />
      </header>

      <div className="ed-switch" role="tablist" aria-label="Pane">
        <button role="tab" aria-selected={pane === "edit"} onClick={() => setPane("edit")}>Edit</button>
        <button role="tab" aria-selected={pane === "review"} onClick={() => setPane("review")}>
          Checks{issueCount > 0 && <span className="count">{issueCount}</span>}
        </button>
      </div>

      <div className="ed-main">
        <section className="ed-canvas" aria-label="Resume">
          {multiCol && (
            <p className="notice" role="note">
              <WarningCircle size={18} weight="fill" />
              <span><strong>Your PDF uses more than one column.</strong> We read it in reading order. Check that each section kept its own content.</span>
            </p>
          )}
          {r.error && <p className="notice notice-error" role="alert"><WarningCircle size={18} weight="fill" /><span>{r.error}</span></p>}
          <div className="ed-toolbar" role="toolbar" aria-label="Edit">
            <button type="button" className="icon-btn" aria-label="Undo" disabled={!r.canUndo} onClick={r.undo}><ArrowArcLeft size={17} /></button>
            <button type="button" className="icon-btn" aria-label="Redo" disabled={!r.canRedo} onClick={r.redo}><ArrowArcRight size={17} /></button>
            <span className="tb-sep" aria-hidden="true" />
            <AddSectionMenu onAdd={addSection} />
          </div>
          <div className="ed-scroll" ref={scroller} id="main">
            <ResumePage doc={doc} update={update} issues={issues} />
          </div>
        </section>

        <aside className="ed-review" aria-label="Review">
          <div className="seg seg-tabs" role="tablist" aria-label="Review views">
            <button role="tab" aria-selected={tab === "checks"} onClick={() => setTab("checks")}>
              Checks{issueCount > 0 && <span className="count">{issueCount}</span>}
            </button>
            <button role="tab" aria-selected={tab === "parser"} onClick={() => setTab("parser")}>What parsers see</button>
          </div>
          <div className="review-body">
            {tab === "checks"
              ? <ChecksPanel scored={r.scored} original={r.meta.original} scoring={r.scoring} onJump={toJump} />
              : <ParserView scored={r.scored} originalText={r.meta.originalText} onJump={toJump} />}
          </div>
        </aside>
      </div>

      {toast && <p className="toast" role="status"><CheckCircle size={18} weight="fill" /> {toast}</p>}

      {/* Printed as the PDF export: text-based, single column, nothing else on the page. */}
      <div className="print-only" aria-hidden="true"><Preview doc={doc} /></div>
    </div>
  );
}
