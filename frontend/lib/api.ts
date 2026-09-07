const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
export type Quality = "exact" | "contextual" | "family";
export type Requirement = { id: string; text: string; kind: string; required: boolean; source_text: string; jd_start: number; jd_end: number };
export type KeywordGroup = { term: string; kind: string; required: boolean; matched: boolean; resume_term: string | null };
export type AtsDimension = { key: string; label: string; score: number; weight: number; detail: string; evidence: string[] };
export type AtsRecommendation = { severity: "high" | "medium" | "low"; code: string; title: string; detail: string; action: string };

export type FitnessResult = {
  ats_score: number;
  ats_grade: string;
  extraction_status: string;
  job_title: string | null;
  dimensions: AtsDimension[];
  recommendations: AtsRecommendation[];
  keyword_coverage: { matched: number; total: number };
  keyword_groups: KeywordGroup[];
  resume_fields: Record<string, string | string[]>;
  sections_found: Record<string, boolean>;
  skills: string[];
  resume_text: string;
  job_description: string;
  checklist_id: string;
  ruleset_version: string;
  ai_available: boolean;
  disclaimer: string;
  scorable: boolean;
};

async function request<T>(path: string, init: RequestInit): Promise<T> {
  let response: Response;
  try { response = await fetch(API_BASE + path, { ...init, signal: AbortSignal.timeout(65000) }); }
  catch { throw new Error("Could not reach the analysis service. Check that the backend is running and try again."); }
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(typeof error?.detail === "string" ? error.detail : "The service could not complete this request. Please try again.");
  }
  return response.json();
}
export async function analyzeFitness(params: { jobDescription: string; file?: File | null; resumeText?: string }): Promise<FitnessResult> {
  const form = new FormData();
  form.append("job_description", params.jobDescription);
  if (params.file) form.append("resume", params.file);
  else form.append("resume_text", params.resumeText ?? "");
  return request("/api/analyze", { method: "POST", body: form });
}
export function suggestRequirements(jobDescription: string) {
  return request<{ status: string; suggestions: Requirement[] }>("/api/requirements/suggest", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ job_description: jobDescription }),
  });
}
