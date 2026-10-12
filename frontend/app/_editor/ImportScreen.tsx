"use client";
import { useRef, useState } from "react";
import Link from "next/link";
import { FileText, UploadSimple, WarningCircle } from "@phosphor-icons/react";
import { SAMPLE } from "../_lib/doc";

const ACCEPT = ".pdf,.docx,.txt,.md,.tex";

export function ImportScreen({ busy, error, onFile, onText, onBlank }: {
  busy: boolean; error: string; onFile: (f: File) => void; onText: (t: string) => void; onBlank: () => void;
}) {
  const [tab, setTab] = useState<"upload" | "paste">("upload");
  const [text, setText] = useState("");
  const [over, setOver] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  return (
    <div className="import">
      <div className="import-inner">
        <Link href="/" className="wordmark import-brand"><span className="wordmark-mark">F</span>FairHire</Link>
        <h1 className="display">Start with the resume<br />you have.</h1>
        <p className="import-lede">We’ll rebuild it as structured fields and show you what a tracking system reads.</p>

        <div className="seg seg-lg" role="tablist" aria-label="How to add your resume">
          <button role="tab" aria-selected={tab === "upload"} onClick={() => setTab("upload")}>Upload a file</button>
          <button role="tab" aria-selected={tab === "paste"} onClick={() => setTab("paste")}>Paste text</button>
        </div>

        {tab === "upload" ? (
          <div
            className={`drop ${over ? "is-over" : ""} ${busy ? "is-busy" : ""}`}
            onDragOver={e => { e.preventDefault(); setOver(true); }}
            onDragLeave={() => setOver(false)}
            onDrop={e => { e.preventDefault(); setOver(false); const f = e.dataTransfer.files[0]; if (f && !busy) onFile(f); }}
          >
            <input ref={input} type="file" accept={ACCEPT} className="sr-only" aria-label="Resume file"
              onChange={e => { const f = e.target.files?.[0]; if (f) onFile(f); e.target.value = ""; }} />
            {busy ? (
              <><span className="spinner" aria-hidden="true" /><p className="drop-title">Reading your resume…</p><p className="drop-sub">Extracting text and rebuilding the structure.</p></>
            ) : (
              <>
                <UploadSimple size={34} aria-hidden="true" />
                <p className="drop-title">{over ? "Release to upload" : "Drop your resume here"}</p>
                <p className="drop-sub">PDF, DOCX, TXT, Markdown — up to 10 MB</p>
                {!over && <button type="button" className="btn btn-primary" onClick={() => input.current?.click()}>Choose a file</button>}
              </>
            )}
          </div>
        ) : (
          <div className="paste">
            <label htmlFor="paste" className="sr-only">Resume text</label>
            <textarea id="paste" className="input paste-area mono" rows={12} value={text} onChange={e => setText(e.target.value)}
              placeholder={"Paste your resume text here.\n\nKeep your headings and line breaks — they help us find the structure."} />
            <div className="paste-actions">
              <button type="button" className="btn btn-quiet" onClick={() => setText(SAMPLE)}><FileText size={16} /> Use a sample</button>
              <button type="button" className="btn btn-primary" disabled={busy || !text.trim()} onClick={() => onText(text)}>
                {busy ? "Reading…" : "Parse my resume"}
              </button>
            </div>
          </div>
        )}

        {error && <p className="notice notice-error" role="alert"><WarningCircle size={18} weight="fill" /><span>{error}</span></p>}

        <p className="import-alt">
          No resume yet? <button type="button" className="link-btn" onClick={onBlank}>Start from a blank page</button>
        </p>
        <p className="fine-print">Uploads are read in memory and not kept. Your draft is saved only in this browser.</p>
      </div>
    </div>
  );
}
