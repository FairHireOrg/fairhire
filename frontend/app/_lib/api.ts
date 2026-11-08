import type { Imported, ResumeDoc, Scored } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://144.126.209.214:8000";
const UNREACHABLE = "Can't reach the FairHire service. Make sure the backend is running, then try again.";

async function call<T>(path: string, init: RequestInit, parse: (r: Response) => Promise<T>): Promise<T> {
  let res: Response;
  try { res = await fetch(BASE + path, { ...init, signal: init.signal ?? AbortSignal.timeout(60000) }); }
  catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw new Error(UNREACHABLE);
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(typeof body?.detail === "string" ? body.detail : "Something went wrong. Please try again.");
  }
  return parse(res);
}

export function importFile(file: File): Promise<Imported> {
  const form = new FormData();
  form.append("resume", file);
  return call("/api/resume/import", { method: "POST", body: form }, r => r.json());
}

export function importText(text: string): Promise<Imported> {
  const form = new FormData();
  form.append("resume_text", text);
  return call("/api/resume/import", { method: "POST", body: form }, r => r.json());
}

export function scoreDocument(document: ResumeDoc, signal?: AbortSignal): Promise<Scored> {
  return call("/api/resume/score", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ document }), signal,
  }, r => r.json());
}

export function exportDocument(document: ResumeDoc, format: "docx" | "txt"): Promise<Blob> {
  return call("/api/resume/export", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ document, format }),
  }, r => r.blob());
}
