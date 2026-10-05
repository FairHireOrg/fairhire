"use client";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import Link from "next/link";
import dynamic from "next/dynamic";
import { parseJevText } from "@/lib/jev";
import { readResumeSource, writeResumeSource, type ResumeSource, type PdfEdits } from "@/lib/resume-source";
import { Sidebar, SidebarContent, SidebarHeader, SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import "./report.css";
import { useEffect, useState, useCallback, useRef, type CSSProperties } from "react";
import { analyzeFitness, exportDocument, putDocument, type ResumeDocument } from "@/lib/api";
import { REPORT_KEY, standardizeResume, type ResumeReport } from "@/lib/report";
const PdfLayoutEditor = dynamic(() => import("@/components/PdfLayoutEditor"), { ssr: false });
export default function ReportPage() {
    const [report, setReport] = useState<ResumeReport | null>(null);
    const [source, setSource] = useState<ResumeSource | null>(null);
    const [sourceFile, setSourceFile] = useState<File | null>(null);
    const [sourceLoading, setSourceLoading] = useState(false);
    const pdfText = useRef("");
    const pendingPdfEdits = useRef<PdfEdits>({});
    const pdfReady = useRef(false);
    const savingRef = useRef(false);
    const [doc, setDoc] = useState<ResumeDocument | null>(null);
    const [ready, setReady] = useState(false);
    const [dirty, setDirty] = useState(false);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState("");
    useEffect(() => {
        const frame = requestAnimationFrame(() => {
            try {
                const saved = sessionStorage.getItem(REPORT_KEY);
                if (saved) {
                    const result: ResumeReport = JSON.parse(saved);
                    setReport(result);
                    setDoc(result.document);
                }
            }
            catch {
                setError("Could not restore the report. Upload your resume again.");
            }
            setReady(true);
        });
        return () => cancelAnimationFrame(frame);
    }, []);
    useEffect(() => {
        if (!report?.sourcePdfId) return;
        let cancelled = false;
        const frame = requestAnimationFrame(() => setSourceLoading(true));
        readResumeSource(report.sourcePdfId).then(saved => {
            if (cancelled) return;
            if (!saved) throw new Error("Could not restore the uploaded resume.");
            setSource(saved);
            pendingPdfEdits.current = saved.edits;
            setSourceFile(new File([saved.bytes], saved.name, { type: saved.type || "application/pdf" }));
        }).catch(e => { if (!cancelled) setError(e instanceof Error ? e.message : "Could not restore the uploaded resume."); })
          .finally(() => { if (!cancelled) { cancelAnimationFrame(frame); setSourceLoading(false); } });
        return () => { cancelled = true; cancelAnimationFrame(frame); };
    }, [report?.sourcePdfId]);
    const extractPdfText = useCallback((text: string) => { pdfText.current = text; pdfReady.current = true; }, []);
    const changePdf = useCallback((text: string, edits: PdfEdits) => {
        pdfText.current = text;
        pendingPdfEdits.current = edits;
        setDirty(true);
    }, []);
    function change(next: ResumeDocument) { setDoc(next); setDirty(true); }
    async function save(download = false) {
        if (!doc || !report || savingRef.current) return;
        if (sourceFile && !pdfReady.current) { setError("Rendering PDF pages..."); return; }
        savingRef.current = true;
        setBusy(true);
        setError("");
        try {
            let next: ResumeReport;
            let exportSource: ResumeDocument;
            if (source && sourceFile) {
                const hasEdits = Object.keys(pendingPdfEdits.current).length > 0;
                const refreshed = await analyzeFitness({ jobDescription: report.job_description, ...(hasEdits ? { resumeText: pdfText.current } : { file: sourceFile }) });
                const parsed = await parseJevText(refreshed.resume_text);
                exportSource = standardizeResume(parsed.resume, refreshed.document);
                next = { ...refreshed, document: exportSource, sourcePdfId: source.id };
                const saved = { ...source, edits: pendingPdfEdits.current };
                await writeResumeSource(saved);
                setSource(saved);
            } else {
                const scored = await putDocument(doc);
                const refreshed = await analyzeFitness({ jobDescription: report.job_description, resumeText: scored.resume_text });
                exportSource = scored.document;
                next = { ...refreshed, document: exportSource };
            }
            sessionStorage.setItem(REPORT_KEY, JSON.stringify(next));
            setReport(next);
            setDoc(next.document);
            setDirty(false);
            if (download) {
                const blob = await exportDocument(exportSource);
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = "resume-ats.docx";
                a.click();
                setTimeout(() => URL.revokeObjectURL(url), 5000);
            }
        } catch (e) { setError(e instanceof Error ? e.message : "Could not update the report."); }
        finally { savingRef.current = false; setBusy(false); }
    }
    function field(label: string, value: string, update: (value: string) => void, multiline = false) {
        const className = "resume-text-box border-transparent shadow-none hover:border-input hover:bg-muted/50 focus-visible:border-ring";
        return <Label className="report-field"><span className="sr-only">{label}</span>{multiline ? <Textarea className={className + " min-h-0 resize-none"} disabled={busy} aria-label={label} placeholder={label} value={value} onChange={e => update(e.target.value)} rows={1}/> : <Input className={className} disabled={busy} aria-label={label} placeholder={label} value={value} onChange={e => update(e.target.value)}/>}</Label>;
    }
    if (!ready)
        return <main><p role="status">Loading your report…</p></main>;
    if (!doc || !report)
        return <main><h1>Upload a resume to begin</h1>{error && <p role="alert">{error}</p>}<Link href="/">Back to upload</Link></main>;
    const checks = { Email: !!doc.contact.email, Name: !!doc.contact.name, Links: !!(doc.contact.linkedin || doc.contact.github), School: doc.education.some(e => !!e.school) };
    return <SidebarProvider defaultOpen={true} className="report-workspace flex-col" style={{ "--sidebar-width": "28rem" } as CSSProperties}>
      <header className="report-header">
        <Button variant="ghost" asChild><Link href="/">← Upload another resume</Link></Button>
        <SidebarTrigger aria-controls="report-overview" />
      </header>
      <div className="flex flex-1 min-w-0 w-full">
        <SidebarInset><main className="report-shell">
          {error && <p role="alert">{error}</p>}
          {sourceLoading ? <p role="status">Rendering PDF pages...</p> : sourceFile ? <PdfLayoutEditor file={sourceFile} initialEdits={source?.edits} disabled={busy} onTextExtracted={extractPdfText} onChange={changePdf} /> : <Card className="report-paper" aria-label="Standardized resume editor">
            <div className="resume-name">{field("Name", doc.contact.name, name => change({ ...doc, contact: { ...doc.contact, name } }))}</div>
            <div className="resume-contact">
              {Object.entries(doc.contact).filter(([key]) => key !== "name").map(([key, value]) => <div key={key}>{field(key, value, v => change({ ...doc, contact: { ...doc.contact, [key]: v } }))}</div>)}
            </div>
            <h2>Summary</h2>{field("Summary", doc.summary, summary => change({ ...doc, summary }), true)}
            <h2>Work experience</h2>
            {doc.experience.map((item, i) => {
              const patch = (key: keyof typeof item, value: string | string[]) => change({ ...doc, experience: doc.experience.map((entry, index) => index === i ? { ...entry, [key]: value } : entry) });
              return <div className="report-entry" key={i}>
                <div className="resume-role-heading">
                  {field("title", item.title, v => patch("title", v))}
                  {field("company", item.company, v => patch("company", v))}
                </div>
                <div className="resume-role-meta">
                  {field("location", item.location, v => patch("location", v))}
                  {field("start", item.start, v => patch("start", v))}
                  {field("end", item.end, v => patch("end", v))}
                </div>
                {field("bullets", item.bullets.map(b => "• " + b).join("\n"), v => patch("bullets", v.split("\n").map(b => b.replace(/^•\s?/, ""))), true)}
                <Button size="sm" variant="ghost" disabled={busy} onClick={() => change({ ...doc, experience: doc.experience.filter((_, index) => index !== i) })}>Remove role</Button>
              </div>;
            })}
            <Button variant="outline" className="w-full" disabled={busy} onClick={() => change({ ...doc, experience: [...doc.experience, { title: "", company: "", location: "", start: "", end: "", bullets: [] }] })}>Add role</Button>
            <h2>Education</h2>
            {doc.education.map((item, i) => {
              const patch = (key: keyof typeof item, value: string) => change({ ...doc, education: doc.education.map((entry, index) => index === i ? { ...entry, [key]: value } : entry) });
              return <div className="report-entry" key={i}>
                <div className="resume-role-heading">{field("degree", item.degree, v => patch("degree", v))}</div>
                <div className="resume-education-meta">{field("school", item.school, v => patch("school", v))}{field("year", item.year, v => patch("year", v))}</div>
                <Button size="sm" variant="ghost" disabled={busy} onClick={() => change({ ...doc, education: doc.education.filter((_, index) => index !== i) })}>Remove education</Button>
              </div>;
            })}
            <Button variant="outline" className="w-full" disabled={busy} onClick={() => change({ ...doc, education: [...doc.education, { degree: "", school: "", year: "" }] })}>Add education</Button>
            {(["skills", "certifications", "projects"] as const).map(key => <div key={key}><h2>{key}</h2>{field(key + " (one per line)", doc[key].join("\n"), v => change({ ...doc, [key]: v.split("\n") }), true)}</div>)}
          </Card>}
        </main></SidebarInset>
        <Sidebar id="report-overview" side="right" collapsible="offcanvas" className="report-sidebar">
          <SidebarHeader className="report-overview-header"><h1>Overview</h1><SidebarTrigger className="md:hidden" /></SidebarHeader>
          <SidebarContent className="report-overview">
            <h2>ATS quality</h2><p>{report.scorable ? `${Math.round(report.ats_score)}/100 · ${report.ats_grade}` : "Not enough readable content to score"}</p>
            {dirty && <p role="status">Resume edited. Update the report to refresh scores.</p>}
            {report.dimensions.map(d => <div className="report-dimension" key={d.key}><div>{d.label}<span>{Math.round(d.score)}/100</span></div><Progress aria-label={d.label} value={d.score}/><p>{d.detail}</p></div>)}
            <h2>ATS readability</h2>{Object.entries(checks).map(([label, found]) => <div className="report-check" key={label}><span aria-label={found ? "Found" : "Missing"}>{found ? "✓" : "✕"}</span>{label}</div>)}
            {report.recommendations.length > 0 && <><h2>Recommendations</h2>{report.recommendations.map((r, i) => <div className="report-dimension" key={i}><strong>{r.title}</strong><p>{r.detail}</p><p>{r.action}</p></div>)}</>}
            <Button disabled={busy || sourceLoading} onClick={() => void save()}>{busy ? "Processing…" : "Update report"}</Button>
            <Button variant="outline" disabled={busy || sourceLoading} onClick={() => void save(true)}>Download DOCX</Button>
          </SidebarContent>
        </Sidebar>
      </div>
    </SidebarProvider>;
}
