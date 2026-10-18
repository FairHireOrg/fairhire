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
    <div className="grid justify-items-center gap-5">
      <label
        className={`grid w-full cursor-pointer justify-items-center gap-1 rounded-(--r-lg) px-6 py-10 text-center transition-[border-color,background] duration-120 focus-within:shadow-(--focus) ${
          over ? "border-2 border-accent bg-accent-soft" : "border-[1.5px] border-dashed border-rule-strong bg-surface hover:border-ink-3"
        }`}
        onDragOver={e => { e.preventDefault(); setOver(true); }}
        onDragLeave={() => setOver(false)}
        onDrop={e => { e.preventDefault(); setOver(false); take(e.dataTransfer.files[0]); }}
      >
        <input
          ref={input} type="file" accept={ACCEPT} className="sr-only" aria-label="Choose your resume file"
          onChange={e => { take(e.target.files?.[0]); e.target.value = ""; }}
        />
        <UploadSimple size={30} aria-hidden="true" className="mb-1.5 text-accent-text" />
        <span className="text-[19px] font-semibold">{over ? "Release to upload" : "Drop your resume here"}</span>
        <span className="font-semibold text-accent-text">or choose a file</span>
        <span className="mt-1.5 text-[13px] text-ink-3">PDF, DOCX, plain text or Markdown</span>
      </label>
      <div className="flex flex-wrap items-center justify-center gap-x-5 gap-y-3">
        <Link href="/editor" className="btn btn-primary">Open the editor</Link>
        <Link href="/editor?new=1" className="link-btn">or start from a blank page</Link>
      </div>
    </div>
  );
}
