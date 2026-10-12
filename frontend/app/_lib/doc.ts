import type { Contact, Entry, ResumeDoc, Section, SectionKind } from "./types";

export const uid = () => (globalThis.crypto?.randomUUID?.() ?? Math.random().toString(36).slice(2)).slice(0, 12);

export const KIND_LABEL: Record<SectionKind, string> = {
  experience: "Work experience", education: "Education", projects: "Projects", skills: "Skills",
  publications: "Publications", certifications: "Certifications", awards: "Awards", custom: "Other section",
};

/** Field labels differ by section so the form says what the field means there. */
export const ENTRY_LABELS: Record<SectionKind, { heading: string; subheading: string; detail: string }> = {
  experience: { heading: "Job title", subheading: "Company", detail: "Extra" },
  education: { heading: "Degree", subheading: "School", detail: "GPA, honors" },
  projects: { heading: "Project", subheading: "Role", detail: "Tech used" },
  publications: { heading: "Title", subheading: "Venue", detail: "Extra" },
  certifications: { heading: "Certification", subheading: "Issuer", detail: "Extra" },
  awards: { heading: "Award", subheading: "Awarded by", detail: "Extra" },
  custom: { heading: "Heading", subheading: "Subheading", detail: "Extra" },
  skills: { heading: "", subheading: "", detail: "" },
};

export const emptyContact: Contact = { name: "", headline: "", email: "", phone: "", location: "", links: [], other: [] };
export const emptyDoc = (): ResumeDoc => ({ contact: { ...emptyContact }, summary: "", sections: [] });

export const newEntry = (): Entry => ({
  id: uid(), heading: "", subheading: "", location: "", start: "", end: "", link: "", detail: "", bullets: [""],
});

export function newSection(kind: SectionKind): Section {
  return {
    id: uid(), kind, title: KIND_LABEL[kind],
    entries: kind === "skills" ? [] : [newEntry()],
    groups: kind === "skills" ? [{ label: "", items: [] }] : [],
  };
}

export function isBlank(doc: ResumeDoc): boolean {
  const c = doc.contact;
  return !doc.summary && !doc.sections.length && !c.name && !c.email && !c.phone;
}

const MONTH_YEAR = /^(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+)?(?:19|20)\d{2}$|^(?:present|current)$/i;
/** Parsers read "Jun 2024" and "June 2024" equally; bare words and numeric styles are the risky ones. */
export const dateLooksSafe = (v: string) => !v.trim() || MONTH_YEAR.test(v.trim());

export const SAMPLE = `Morgan Rivera
Backend Engineer
morgan.rivera@example.com | (415) 555-0132 | San Francisco, CA | linkedin.com/in/morganrivera

Summary
Backend engineer with six years of experience building reliable services for small businesses.

Experience
Senior Backend Engineer | Harbor Software | San Francisco, CA | March 2022 – Present
- Built Python services that reduced processing time by 32%
- Designed REST APIs for a customer reporting platform used by 40 accounts
Backend Engineer | Brightline Labs | June 2019 – February 2022
- Maintained PostgreSQL databases serving 2M requests per day
- Wrote integration tests that cut regressions by half

Education
B.S. Computer Science | River Valley University | May 2019

Skills
Languages: Python, Go, SQL
Infrastructure: Docker, Kubernetes, AWS, Postgres`;
