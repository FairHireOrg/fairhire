const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export type JevField = {
  path: string;
  value: unknown;
  confidence: number;
  distribution: Record<string, number>;
  candidates: string[];
  question_type: string;
};

export type JevParseResult = {
  resume: JsonResume;
  fields: Record<string, JevField>;
  engine: string;
  parse_ms: number;
  fallback: boolean;
  service_info: Record<string, unknown>;
};

export type JsonResume = {
  basics?: {
    name?: string;
    label?: string;
    image?: string;
    email?: string;
    phone?: string;
    url?: string;
    summary?: string;
    location?: {
      address?: string;
      postalCode?: string;
      city?: string;
      countryCode?: string;
      region?: string;
    };
    profiles?: { network?: string; username?: string; url?: string }[];
  };
  work?: {
    name?: string;
    position?: string;
    url?: string;
    startDate?: string;
    endDate?: string;
    summary?: string;
    highlights?: string[];
    location?: string;
  }[];
  education?: {
    institution?: string;
    url?: string;
    area?: string;
    studyType?: string;
    startDate?: string;
    endDate?: string;
    score?: string;
    courses?: string[];
  }[];
  skills?: {
    name?: string;
    level?: string;
    keywords?: string[];
  }[];
  projects?: {
    name?: string;
    description?: string;
    highlights?: string[];
    keywords?: string[];
    startDate?: string;
    endDate?: string;
    url?: string;
    roles?: string[];
    entity?: string;
    type?: string;
  }[];
  certifications?: { name?: string; issuer?: string; date?: string; url?: string }[];
  publications?: { name?: string; publisher?: string; releaseDate?: string; url?: string; summary?: string }[];
  languages?: { language?: string; fluency?: string }[];
  interests?: { name?: string; keywords?: string[] }[];
  references?: { name?: string; reference?: string }[];
  awards?: { title?: string; date?: string; awarder?: string; summary?: string }[];
  meta?: Record<string, unknown>;
};

export type ValidationResult = {
  valid: boolean;
  errors: string[];
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(API_BASE + path, { ...init, signal: AbortSignal.timeout(120000) });
  } catch {
    throw new Error("Could not reach the analysis service. Check that the backend is running and try again.");
  }
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(typeof error?.detail === "string" ? error.detail : "The service could not complete this request. Please try again.");
  }
  return response.json();
}

export function jevHealth() {
  return request<{ available: boolean; url: string; detail: Record<string, unknown> }>("/api/jev/health", { method: "GET" });
}

export function parseJevText(resumeText: string) {
  return request<JevParseResult>("/api/parse/jev", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ resume_text: resumeText }),
  });
}

export async function parseJevPdf(file: File): Promise<JevParseResult> {
  const form = new FormData();
  form.append("resume", file);
  let response: Response;
  try {
    response = await fetch(API_BASE + "/api/parse/jev/pdf", {
      method: "POST",
      body: form,
      signal: AbortSignal.timeout(120000),
    });
  } catch {
    throw new Error("Could not reach the analysis service. Check that the backend is running and try again.");
  }
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(typeof error?.detail === "string" ? error.detail : "The service could not complete this request. Please try again.");
  }
  return response.json();
}

export async function exportJevDocx(resume: JsonResume): Promise<Blob> {
  let response: Response;
  try {
    response = await fetch(API_BASE + "/api/jev/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ document: resume }),
      signal: AbortSignal.timeout(65000),
    });
  } catch {
    throw new Error("Could not reach the analysis service. Check that the backend is running and try again.");
  }
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(typeof error?.detail === "string" ? error.detail : "The service could not complete this request. Please try again.");
  }
  return response.blob();
}

export function validateJsonResume(resume: unknown): ValidationResult {
  try {
    const validator = require("@jsonresume/schema");
    const result = validator.validate(resume);
    if (result.valid) return { valid: true, errors: [] };
    const errors = (result.errors || []).map((e: { message?: string; path?: string }) => {
      const path = e.path ? `${e.path}: ` : "";
      return `${path}${e.message || "invalid"}`;
    });
    return { valid: false, errors };
  } catch (e) {
    return { valid: false, errors: [e instanceof Error ? e.message : "Schema validation failed"] };
  }
}
