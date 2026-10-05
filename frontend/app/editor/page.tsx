"use client";
import { Progress } from "@/components/ui/progress";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useState, useCallback, useRef } from "react";
import Link from "next/link";
import { Sidebar, SidebarContent, SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { ArrowLeft, ArrowRight, DownloadSimple, FileText, Info, ShieldCheck, UploadSimple, X, } from "@phosphor-icons/react";
import ResumeEditor from "@/components/ResumeEditor";
import PdfLayoutEditor from "@/components/PdfLayoutEditor";
import { parseJevText, parseJevPdf, exportJevDocx, validateJsonResume, type JsonResume, type JevParseResult, } from "@/lib/jev";
const SAMPLE = `Morgan Rivera
morgan.rivera@example.com
+1 (415) 555-0132
San Francisco, CA
linkedin.com/in/morganrivera

Summary
Backend engineer building reliable services for small businesses. 6 years of experience with Python and distributed systems.

Skills
Python, PostgreSQL, REST APIs, Docker, Kubernetes, Git, AWS

Experience
Senior Backend Engineer | Harbor Software | 2022 - 2026
- Built Python services that reduced processing time by 32%.
- Designed REST APIs for a customer reporting platform.
- Deployed Docker containers with automated health checks.

Backend Engineer | Brightline Labs | 2019 - 2022
- Maintained PostgreSQL databases serving 2M requests per day.
- Wrote integration tests that cut regressions by half.

Education
Bachelor of Science in Computer Science
River Valley University | 2015 - 2019

Certifications
AWS Certified Solutions Architect`;
type Mode = "quill" | "pdf";
export default function EditorPage() {
    const [mode, setMode] = useState<Mode>("quill");
    const [resumeText, setResumeText] = useState("");
    const [pdfFile, setPdfFile] = useState<File | null>(null);
    const [resume, setResume] = useState<JsonResume>({ basics: {} });
    const [parseResult, setParseResult] = useState<JevParseResult | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [exporting, setExporting] = useState(false);
    const [showJson, setShowJson] = useState(false);
    const fileInput = useRef<HTMLInputElement>(null);
    const validation = validateJsonResume(resume);
    const handleParse = useCallback(async () => {
        setError("");
        setParseResult(null);
        if (mode === "pdf" && pdfFile) {
            setLoading(true);
            try {
                const result = await parseJevPdf(pdfFile);
                setResume(result.resume);
                setParseResult(result);
            }
            catch (e) {
                setError(e instanceof Error ? e.message : "Failed to parse PDF");
            }
            finally {
                setLoading(false);
            }
        }
        else if (resumeText.trim()) {
            setLoading(true);
            try {
                const result = await parseJevText(resumeText);
                setResume(result.resume);
                setParseResult(result);
            }
            catch (e) {
                setError(e instanceof Error ? e.message : "Failed to parse text");
            }
            finally {
                setLoading(false);
            }
        }
        else {
            setError("Paste resume text or upload a PDF first.");
        }
    }, [mode, pdfFile, resumeText]);
    const handlePdfText = useCallback((text: string) => {
        setResumeText(text);
    }, []);
    const handleExportJson = useCallback(() => {
        const blob = new Blob([JSON.stringify(resume, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${(resume.basics?.name || "resume").toLowerCase().replace(/\s+/g, "-")}.json`;
        a.click();
        setTimeout(() => URL.revokeObjectURL(url), 5000);
    }, [resume]);
    const handleExportDocx = useCallback(async () => {
        setExporting(true);
        setError("");
        try {
            const blob = await exportJevDocx(resume);
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `${(resume.basics?.name || "resume").toLowerCase().replace(/\s+/g, "-")}-ats.docx`;
            a.click();
            setTimeout(() => URL.revokeObjectURL(url), 5000);
        }
        catch (e) {
            setError(e instanceof Error ? e.message : "Export failed");
        }
        finally {
            setExporting(false);
        }
    }, [resume]);
    return (<SidebarProvider className="app-shell">
      <Sidebar collapsible="offcanvas"><SidebarContent className="p-4">
        <Link className="brand" href="/">
          <span className="brand-icon">
            <FileText size={23} weight="bold"/>
          </span>
          FairHire
        </Link>
        <span className="sidebar-label">Editor</span>
        <Button className="nav-item active" onClick={() => setMode("quill")} variant="ghost">
          <FileText size={19}/>
          WYSIWYG Editor
        </Button>
        <Button className="nav-item" onClick={() => setMode("pdf")} variant="ghost">
          <UploadSimple size={19}/>
          PDF Layout Editor
        </Button>
        <div className="sidebar-bottom">
          <div className="sidebar-note">
            <ShieldCheck size={23}/>
            <h3>Schema-first.</h3>
            <p>Every edit maps to the JSON Resume schema.</p>
          </div>
          <span className="sidebar-foot">Quill 2.0.3 + NanoJev parsing</span>
        </div>
      </SidebarContent></Sidebar>

      <SidebarInset className="app-body">
        <header className="topbar"><SidebarTrigger className="order-last" />
          <div className="breadcrumb">
            <Link href="/" style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <ArrowLeft size={14}/> Workspace
            </Link>
            <span>/</span>
            <strong>Resume Editor</strong>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <Button className="text-button" onClick={() => setShowJson(!showJson)} variant="ghost">
              {showJson ? "Hide" : "Show"} JSON
            </Button>
            <Button className="text-button" onClick={handleExportJson} variant="ghost">
              <DownloadSimple size={14}/> JSON
            </Button>
            <Button className="text-button" onClick={handleExportDocx} disabled={exporting} variant="ghost">
              <DownloadSimple size={14}/> DOCX
            </Button>
          </div>
        </header>

        <main id="main" style={{ maxWidth: 1200 }}>
          <div className="page-heading">
            <div>
              <p className="eyebrow">Resume Editor</p>
              <h1>Edit your resume, schema-backed.</h1>
              <p>
                Paste text or upload a PDF. NanoJev parses it into the JSON Resume schema. Edit in the WYSIWYG
                editor or preserve the exact PDF layout.
              </p>
            </div>
          </div>

          <div className="input-grid" style={{ gridTemplateColumns: "1fr" }}>
            <Card className="input-panel">
              <div className="input-heading">
                <div>
                  <span className="step-number">1</span>
                  <h2>Input</h2>
                </div>
                <ToggleGroup type="single" value={mode} onValueChange={value => { if (value) setMode(value as Mode); }} variant="outline" aria-label="Editor mode">
                  <ToggleGroupItem value="quill">
                    WYSIWYG
                  </ToggleGroupItem>
                  <ToggleGroupItem value="pdf">
                    PDF Layout
                  </ToggleGroupItem>
                </ToggleGroup>
              </div>

              {mode === "quill" ? (<>
                  <Textarea value={resumeText} onChange={(e) => setResumeText(e.target.value)} placeholder="Paste your resume text here..." rows={8} aria-label="Resume text input"/>
                  <div style={{ marginTop: 8 }}>
                    <Button className="button secondary" onClick={() => setResumeText(SAMPLE)} variant="outline">
                      Load sample
                    </Button>
                  </div>
                </>) : (<div className="upload-area" onDragOver={(e) => e.preventDefault()} onDrop={(e) => {
                e.preventDefault();
                const f = e.dataTransfer.files[0];
                if (f && f.name.endsWith(".pdf")) {
                    setPdfFile(f);
                    setError("");
                }
                else {
                    setError("Please drop a PDF file.");
                }
            }}>
                  <Input ref={fileInput} type="file" accept=".pdf" className="file-input" onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) {
                    setPdfFile(f);
                    setError("");
                }
            }}/>
                  <span className="upload-icon">
                    {pdfFile ? <FileText size={30}/> : <UploadSimple size={30}/>}
                  </span>
                  <h3>{pdfFile ? pdfFile.name : "Drop a PDF here"}</h3>
                  <p>{pdfFile ? `${(pdfFile.size / 1024).toFixed(0)} KB` : "PDF files only"}</p>
                  <Button type="button" className="button secondary" onClick={() => fileInput.current?.click()} variant="outline">
                    Browse files
                  </Button>
                </div>)}

              <div className="input-footer">
                <span>{mode === "quill" ? "Paste any resume text" : "PDF rendered with exact layout"}</span>
                <span>{resumeText.length.toLocaleString()} chars</span>
              </div>
            </Card>
          </div>

          <div className="analyze-bar">
            <p>
              <ShieldCheck size={18}/> Parsed by NanoJev into JSON Resume schema.
            </p>
            <Button className="button primary analyze-button" onClick={handleParse} disabled={loading} variant="default">
              {loading ? (<>
                  <span className="spinner"/> Parsing...
                </>) : (<>
                  Parse with NanoJev <ArrowRight size={18}/>
                </>)}
            </Button>
            {error && (<Alert variant="destructive" className="error-message">
                <Info size={19}/>
                <span>{error}</span>
              </Alert>)}
          </div>

          {parseResult && !loading && (<div className="notice" role="status" style={{ marginBottom: 20 }}>
              Parsed in {parseResult.parse_ms.toFixed(0)}ms via {parseResult.engine}
              {parseResult.fallback ? " (deterministic fallback)" : ""}.{" "}
              {Object.keys(parseResult.fields).length} fields with confidence scores.
            </div>)}

          <div className="results" style={{ gridTemplateColumns: "1fr" }}>
            <Card className="editor-panel">
              <div className="section-heading">
                <div>
                  <h2>Editor</h2>
                  <p>
                    {mode === "quill"
            ? "WYSIWYG editor with JSON Resume block schema. Use the toolbar to add blocks."
            : "Exact-layout PDF editor. Click any text to edit in place."}
                  </p>
                </div>
                {mode === "quill" && (<Badge className={`badge ${validation.valid ? "success" : "warning"}`}>
                    {validation.valid ? "Schema valid" : `${validation.errors.length} issue${validation.errors.length !== 1 ? "s" : ""}`}
                  </Badge>)}
              </div>

              {mode === "quill" ? (<ResumeEditor resume={resume} onChange={setResume}/>) : pdfFile ? (<PdfLayoutEditor file={pdfFile} onTextExtracted={handlePdfText}/>) : (<p className="muted">Upload a PDF to use the layout editor.</p>)}
            </Card>

            {showJson && (<Card className="editor-panel">
                <div className="section-heading">
                  <div>
                    <h2>JSON Resume</h2>
                    <p>Live schema-validated output.</p>
                  </div>
                  <Button className="icon-button" onClick={() => setShowJson(false)} aria-label="Close JSON panel" variant="ghost" size="icon">
                    <X size={19}/>
                  </Button>
                </div>
                {!validation.valid && (<Alert variant="destructive" className="error-message" style={{ marginBottom: 12 }}>
                    <ul style={{ margin: 0, paddingLeft: 16 }}>
                      {validation.errors.slice(0, 5).map((e, i) => (<li key={i}>{e}</li>))}
                    </ul>
                  </Alert>)}
                <pre style={{
                background: "var(--base)",
                padding: 16,
                borderRadius: 8,
                fontSize: 12,
                lineHeight: 1.7,
                maxHeight: 480,
                overflow: "auto",
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
                margin: 0,
            }}>
                  {JSON.stringify(resume, null, 2)}
                </pre>
              </Card>)}

            {parseResult && Object.keys(parseResult.fields).length > 0 && (<Card className="editor-panel">
                <div className="section-heading">
                  <div>
                    <h2>Field Confidence</h2>
                    <p>NanoJev distribution peaks per field.</p>
                  </div>
                </div>
                <div className="profile-grid">
                  {Object.entries(parseResult.fields)
                .filter(([, f]) => f.question_type === "choice" && f.value != null)
                .slice(0, 12)
                .map(([path, f]) => (<div key={path} style={{ marginBottom: 12 }}>
                        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12 }}>
                          <span className="muted">{path}</span>
                          <span className="mono">{(f.confidence * 100).toFixed(0)}%</span>
                        </div>
                        <Progress value={f.confidence * 100} aria-label={path} />
                        <div style={{ fontSize: 12, marginTop: 4, overflowWrap: "anywhere" }}>{String(f.value)}</div>
                      </div>))}
                </div>
              </Card>)}
          </div>

          <footer>
            <span>&copy; 2026 FairHire. JSON Resume schema v1.0.0.</span>
            <Link href="/" className="text-button">
              Back to checker <ArrowUpRight size={14}/>
            </Link>
          </footer>
        </main>
      </SidebarInset>
    </SidebarProvider>);
}
function ArrowUpRight({ size }: {
    size: number;
}) {
    return (<svg width={size} height={size} viewBox="0 0 256 256" fill="currentColor">
      <path d="M200,64V168a8,8,0,0,1-16,0V83.31L69.66,197.66a8,8,0,0,1-11.32-11.32L172.69,72H88a8,8,0,0,1,0-16H192A8,8,0,0,1,200,64Z"/>
    </svg>);
}
