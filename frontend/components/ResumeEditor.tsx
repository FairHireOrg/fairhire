"use client";
import { Input } from "@/components/ui/input";
import { Bold, Italic, Underline, Heading1, Heading2, Heading3, List, ListOrdered, Link as LinkIcon, RemoveFormatting } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useEffect, useRef, useCallback, useState } from "react";
import type { JsonResume } from "@/lib/jev";
const BLOCK_TYPES = [
    { key: "name", label: "Name", tag: "h1" },
    { key: "contact", label: "Contact", tag: "p" },
    { key: "section", label: "Section", tag: "h2" },
    { key: "summary", label: "Summary", tag: "p" },
    { key: "work", label: "Work Entry", tag: "p" },
    { key: "education", label: "Education", tag: "p" },
    { key: "skills", label: "Skills", tag: "p" },
] as const;
type BlockKey = (typeof BLOCK_TYPES)[number]["key"];
function resumeToDelta(resume: JsonResume): {
    ops: Record<string, unknown>[];
} {
    const ops: Record<string, unknown>[] = [];
    const basics = resume.basics || {};
    if (basics.name) {
        ops.push({ insert: basics.name, attributes: { jr: "name" } });
        ops.push({ insert: "\n" });
    }
    const contactBits = [basics.email, basics.phone, basics.url].filter(Boolean) as string[];
    if (contactBits.length) {
        ops.push({ insert: contactBits.join(" | "), attributes: { jr: "contact" } });
        ops.push({ insert: "\n" });
    }
    if (basics.summary) {
        ops.push({ insert: "Summary", attributes: { jr: "section", bold: true } });
        ops.push({ insert: "\n" });
        ops.push({ insert: basics.summary, attributes: { jr: "summary" } });
        ops.push({ insert: "\n" });
    }
    for (const w of resume.work || []) {
        const header = [w.position, w.name, [w.startDate, w.endDate].filter(Boolean).join(" – ")]
            .filter(Boolean)
            .join(" | ");
        if (header) {
            ops.push({ insert: header, attributes: { jr: "work", bold: true } });
            ops.push({ insert: "\n" });
        }
        for (const hl of w.highlights || []) {
            ops.push({ insert: hl, attributes: { jr: "work-bullet", list: "bullet" } });
            ops.push({ insert: "\n" });
        }
    }
    for (const e of resume.education || []) {
        const line = [e.studyType, e.area, e.institution, e.endDate].filter(Boolean).join(", ");
        if (line) {
            ops.push({ insert: line, attributes: { jr: "education" } });
            ops.push({ insert: "\n" });
        }
    }
    const skills = (resume.skills || []).map((s) => s.name).filter(Boolean) as string[];
    if (skills.length) {
        ops.push({ insert: "Skills", attributes: { jr: "section", bold: true } });
        ops.push({ insert: "\n" });
        ops.push({ insert: skills.join(", "), attributes: { jr: "skills" } });
        ops.push({ insert: "\n" });
    }
    return { ops };
}
type QuillLike = {
    root: HTMLElement;
};
function deltaToResume(quill: QuillLike): JsonResume {
    const resume: JsonResume = { basics: {} };
    const lines = quill.root.querySelectorAll("[data-jr]");
    let currentWork: NonNullable<JsonResume["work"]>[number] | null = null;
    lines.forEach((el) => {
        const jr = el.getAttribute("data-jr");
        const text = el.textContent?.trim() || "";
        if (!text)
            return;
        switch (jr) {
            case "name":
                resume.basics!.name = text;
                break;
            case "contact": {
                const parts = text.split("|").map((p) => p.trim());
                for (const p of parts) {
                    if (p.includes("@"))
                        resume.basics!.email = p;
                    else if (/^[\d\s()+.-]+$/.test(p))
                        resume.basics!.phone = p;
                    else if (p.startsWith("http") || p.includes(".com") || p.includes(".dev"))
                        resume.basics!.url = p;
                    else if (!resume.basics!.email && !resume.basics!.phone)
                        resume.basics!.email = p;
                }
                break;
            }
            case "section":
                break;
            case "summary":
                resume.basics!.summary = text;
                break;
            case "work":
                currentWork = { position: text.split("|")[0]?.trim() || text };
                resume.work = resume.work || [];
                resume.work.push(currentWork);
                break;
            case "work-bullet":
                if (currentWork) {
                    currentWork.highlights = currentWork.highlights || [];
                    currentWork.highlights.push(text);
                }
                break;
            case "education": {
                const parts = text.split(",").map((p) => p.trim());
                resume.education = resume.education || [];
                resume.education.push({
                    studyType: parts[0] || "",
                    area: parts[1] || "",
                    institution: parts[2] || "",
                    endDate: parts[3] || "",
                });
                break;
            }
            case "skills": {
                const names = text.split(",").map((s) => s.trim()).filter(Boolean);
                resume.skills = names.map((name) => ({ name }));
                break;
            }
        }
    });
    if (!resume.basics!.name && !resume.basics!.email)
        delete resume.basics;
    return resume;
}
export default function ResumeEditor({ resume, onChange, }: {
    resume: JsonResume;
    onChange: (r: JsonResume) => void;
}) {
    const containerRef = useRef<HTMLDivElement>(null);
    const quillRef = useRef<InstanceType<typeof import("quill").default> | null>(null);
    const [ready, setReady] = useState(false);
    const [showLink, setShowLink] = useState(false);
    const [link, setLink] = useState("");
    const onChangeRef = useRef(onChange);
    onChangeRef.current = onChange;
    useEffect(() => {
        let cancelled = false;
        (async () => {
            const [{ default: Quill, Parchment }] = await Promise.all([
                import("quill"),
                import("quill/dist/quill.snow.css" as string),
            ]);
            if (cancelled || !containerRef.current)
                return;
            const Block = Quill.import("blots/block") as typeof import("quill/blots/block").default;
            class JrBlock extends Block {
                static blotName = "jr-block";
                static tagName = "p";
            }
            Quill.register(JrBlock, true);
            const JrAttributor = new Parchment.Attributor("jr", "data-jr", {
                scope: Parchment.Scope.BLOCK,
            });
            Quill.register(JrAttributor, true);
            const quill = new Quill(containerRef.current, {
                theme: "snow",
                modules: { toolbar: false },
                placeholder: "Start typing or paste a resume...",
            });
            quill.on("text-change", () => {
                const r = deltaToResume(quill);
                onChangeRef.current(r);
            });
            quillRef.current = quill;
            setReady(true);
        })();
        return () => {
            cancelled = true;
            quillRef.current = null;
        };
    }, []);
    useEffect(() => {
        const quill = quillRef.current;
        if (!quill)
            return;
        const current = deltaToResume(quill);
        const currentStr = JSON.stringify(current);
        const newStr = JSON.stringify(resume);
        if (currentStr === newStr)
            return;
        const delta = resumeToDelta(resume);
        quill.setContents(delta.ops, "silent");
    }, [resume, ready]);
    const insertBlock = useCallback((key: BlockKey) => {
        const quill = quillRef.current;
        if (!quill)
            return;
        const range = quill.getSelection(true);
        const labels: Record<BlockKey, string> = {
            name: "Your Name",
            contact: "email@example.com | (555) 123-4567 | City, ST",
            section: "Section Heading",
            summary: "Professional summary...",
            work: "Job Title | Company | 2020 – Present",
            education: "Degree, Field, Institution, Year",
            skills: "Skill 1, Skill 2, Skill 3",
        };
        quill.insertText(range.index, labels[key], { jr: key }, "user");
        quill.insertText(range.index + labels[key].length, "\n", "user");
        quill.setSelection(range.index + labels[key].length + 1, 0, "user");
    }, []);
    function format(name: string, value: string | number | boolean) {
        const quill = quillRef.current;
        if (!quill) return;
        quill.getSelection(true);
        quill.format(name, quill.getFormat()[name] === value ? false : value, "user");
    }
    return (<Card className="resume-editor-wrap">
      <div className="jr-toolbar">
        {BLOCK_TYPES.map((bt) => (<Button key={bt.key} type="button" className="jr-tool-btn" onClick={() => insertBlock(bt.key)} variant="outline">
            + {bt.label}
          </Button>))}
      </div>
      <div className="jr-toolbar" role="toolbar" aria-label="Formatting">
        {[{ label: "bold", name: "bold", value: true, Icon: Bold }, { label: "italic", name: "italic", value: true, Icon: Italic }, { label: "underline", name: "underline", value: true, Icon: Underline }, { label: "header 1", name: "header", value: 1, Icon: Heading1 }, { label: "header 2", name: "header", value: 2, Icon: Heading2 }, { label: "header 3", name: "header", value: 3, Icon: Heading3 }, { label: "bullet", name: "list", value: "bullet", Icon: List }, { label: "ordered", name: "list", value: "ordered", Icon: ListOrdered }].map(({ label, name, value, Icon }) => <Button key={label} type="button" size="icon" variant="ghost" aria-label={label} onMouseDown={e => e.preventDefault()} onClick={() => format(name, value)}><Icon /></Button>)}
        <Button type="button" variant="ghost" size="icon" aria-label="link" onMouseDown={e => e.preventDefault()} onClick={() => setShowLink(!showLink)}><LinkIcon /></Button>
        <Button type="button" variant="ghost" size="icon" aria-label="clean" onMouseDown={e => e.preventDefault()} onClick={() => { const quill = quillRef.current; const range = quill?.getSelection(true); if (quill && range) quill.removeFormat(range.index, range.length, "user"); }}><RemoveFormatting /></Button>
        {showLink && <Input aria-label="link" value={link} onChange={e => setLink(e.target.value)} onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); format("link", link); setShowLink(false); } }}/>} 
      </div>
      <div ref={containerRef} className="quill-container"/>
    </Card>);
}
