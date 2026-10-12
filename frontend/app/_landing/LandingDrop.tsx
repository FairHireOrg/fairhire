"use client";
import { useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { UploadSimple } from "@phosphor-icons/react";
import { parkFile } from "../_lib/handoff";

const ACCEPT = ".pdf,.docx,.txt,.md,.tex";

/**
 * The hero's drop target. The file is parked in memory and the editor imports it on arrival,
 * so nothing is uploaded until the editor opens.
 */
export function LandingDrop() {
  const router = useRouter();
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);

  const take = (f: File | undefined | null) => {
    if (!f) return;
    parkFile(f);
    router.push("/editor");
  };

  return (
    <div className="lp-drop-wrap">
      <label
        className={`lp-drop ${over ? "is-over" : ""}`}
        onDragOver={e => { e.preventDefault(); setOver(true); }}
        onDragLeave={() => setOver(false)}
        onDrop={e => { e.preventDefault(); setOver(false); take(e.dataTransfer.files[0]); }}
      >
        <input
          ref={input} type="file" accept={ACCEPT} className="sr-only" aria-label="Choose your resume file"
          onChange={e => { take(e.target.files?.[0]); e.target.value = ""; }}
        />
        <UploadSimple size={30} aria-hidden="true" />
        <span className="lp-drop-title">{over ? "Release to upload" : "Drop your resume here"}</span>
        <span className="lp-drop-link">or choose a file</span>
        <span className="lp-drop-types">PDF, DOCX, plain text or Markdown</span>
      </label>
      <div className="lp-drop-alt">
        <Link href="/editor" className="btn btn-primary">Open the editor</Link>
        <Link href="/editor?new=1" className="link-btn">or start from a blank page</Link>
      </div>
    </div>
  );
}
