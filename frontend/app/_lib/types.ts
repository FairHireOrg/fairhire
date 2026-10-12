export type SectionKind =
  | "experience" | "education" | "projects" | "skills"
  | "publications" | "certifications" | "awards" | "custom";

export type Contact = {
  name: string; headline: string; email: string; phone: string; location: string;
  links: string[]; other: string[];
};

export type Entry = {
  id: string; heading: string; subheading: string; location: string;
  start: string; end: string; link: string; detail: string; bullets: string[];
};

export type SkillGroup = { label: string; items: string[] };

export type Section = {
  id: string; kind: SectionKind; title: string; entries: Entry[]; groups: SkillGroup[];
};

export type ResumeDoc = { contact: Contact; summary: string; sections: Section[] };

export type Severity = "high" | "medium" | "low";
export type Target = { section: string; entry: string };

export type Recommendation = {
  severity: Severity; code: string; title: string; detail: string; action: string;
  start: number; end: number; line: number; target: Target;
};
export type Dimension = {
  key: string; label: string; score: number; weight: number; detail: string; family: string;
};
export type Ats = { score: number; grade: string; dimensions: Dimension[]; recommendations: Recommendation[] };

export type Scored = {
  document: ResumeDoc;
  text: string;
  owners: Target[];
  ats: Ats;
  ruleset: string;
};

export type Imported = Scored & {
  source: { kind: "pdf" | "docx" | "text"; notes: string[]; filename: string };
  original: Ats;
  original_text: string;
};
