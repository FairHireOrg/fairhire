const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export type DimensionScore = {
  key: string;
  label: string;
  score: number;
  weight: number;
  detail: string;
  evidence: string[];
};

export type Blocker = {
  severity: "high" | "medium" | "low";
  code: string;
  message: string;
  suggestion: string;
};

export type MatchLink = {
  canonical: string;
  jd_term: string;
  resume_term: string;
  category: string;
  required: boolean;
  quality: "exact" | "contains" | "family" | "inferred" | "fuzzy";
  score: number;
  jd_sentence_index: number;
  jd_sentence_text: string;
  jd_start: number;
  jd_end: number;
  resume_sentence_index: number;
  resume_sentence_text: string;
  resume_start: number;
  resume_end: number;
};

export type Sentence = {
  index: number;
  text: string;
  start: number;
  end: number;
};

export type TermRow = {
  term: string;
  kind: string;
  category?: string;
  label?: string;
  required: boolean;
  matched: boolean;
  quality: "exact" | "contains" | "family" | "inferred" | "fuzzy" | null;
  score: number | null;
  resume_term: string | null;
  suggested?: boolean | null;
  hint?: string;
};

export type ConfirmItem = {
  term: string;
  kind: string;
  required: boolean;
  suggested: boolean | null;
  hint: string;
};

export type FitnessResult = {
  overall_score: number;
  extraction_mode: string;
  job_title: string | null;
  dimensions: DimensionScore[];
  blockers: Blocker[];
  links: MatchLink[];
  required_terms: TermRow[];
  optional_terms: TermRow[];
  confirm_items: ConfirmItem[];
  missing_required: string[];
  missing_optional: string[];
  jd_sentences: Sentence[];
  resume_sentences: Sentence[];
  resume_fields: Record<string, string | string[]>;
  resume_titles: string[];
  sections_found: Record<string, boolean>;
  resume_char_count: number;
  jd_features: {
    role_title?: string | null;
    role_summary?: string;
    required_terms?: TermRow[];
    optional_terms?: TermRow[];
  } | null;
  resume_features: {
    email?: string | null;
    phone?: string | null;
    location?: string | null;
    linkedin?: string | null;
    github?: string | null;
    degrees?: string[];
    titles?: string[];
    skills?: string[];
  } | null;
  disclaimer: string;
  resume_text: string;
};

async function readError(res: Response): Promise<string> {
  try {
    const data = await res.json();
    return typeof data.detail === "string"
      ? data.detail
      : JSON.stringify(data.detail ?? data.message ?? res.statusText);
  } catch {
    return res.statusText || "Request failed";
  }
}

export async function analyzeFitness(params: {
  jobDescription: string;
  file?: File | null;
  resumeText?: string;
  confirmations?: Record<string, boolean>;
}): Promise<FitnessResult> {
  const form = new FormData();
  form.append("job_description", params.jobDescription);
  if (params.file) {
    form.append("resume", params.file);
  } else if (params.resumeText) {
    form.append("resume_text", params.resumeText);
  } else {
    throw new Error("Provide a resume file or pasted text");
  }
  if (params.confirmations && Object.keys(params.confirmations).length > 0) {
    form.append("confirmations", JSON.stringify(params.confirmations));
  }

  const res = await fetch(`${API_BASE}/api/analyze`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    throw new Error(await readError(res));
  }
  return res.json();
}

export async function checkHealth(): Promise<{
  status: string;
  mode: string;
  product: string;
}> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) {
    throw new Error(await readError(res));
  }
  return res.json();
}
