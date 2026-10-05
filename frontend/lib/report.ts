import type { JsonResume } from "./jev";
import type { FitnessResult, ResumeDocument } from "./api";

export type ResumeReport = FitnessResult & { sourcePdfId?: string };

export const REPORT_KEY = "fairhire:report:v1";

export function standardizeResume(resume: JsonResume, fallback: ResumeDocument | null): ResumeDocument {
  const b = resume.basics ?? {};
  return {
    contact: {
      name: b.name || fallback?.contact.name || "",
      email: b.email || fallback?.contact.email || "",
      phone: b.phone || fallback?.contact.phone || "",
      location: [b.location?.city, b.location?.region, b.location?.countryCode].filter(Boolean).join(", ") || fallback?.contact.location || "",
      linkedin: b.profiles?.find(p => p.network?.toLowerCase() === "linkedin")?.url || fallback?.contact.linkedin || "",
      github: b.profiles?.find(p => p.network?.toLowerCase() === "github")?.url || fallback?.contact.github || "",
    },
    summary: b.summary || fallback?.summary || "",
    experience: resume.work?.length ? resume.work.map(w => ({ title: w.position ?? "", company: w.name ?? "", location: w.location ?? "", start: w.startDate ?? "", end: w.endDate ?? "", bullets: [...(w.summary ? [w.summary] : []), ...(w.highlights ?? [])] })) : fallback?.experience ?? [],
    education: resume.education?.length ? resume.education.map(e => ({ degree: [e.studyType, e.area].filter(Boolean).join(" "), school: e.institution ?? "", year: [e.startDate, e.endDate].filter(Boolean).join(" – ") })) : fallback?.education ?? [],
    skills: resume.skills?.length ? [...new Set(resume.skills.flatMap(s => [s.name, ...(s.keywords ?? [])].filter((v): v is string => !!v)))] : fallback?.skills ?? [],
    certifications: resume.certifications?.length ? resume.certifications.map(c => [c.name, c.issuer, c.date].filter(Boolean).join(" | ")) : fallback?.certifications ?? [],
    projects: resume.projects?.length ? resume.projects.map(p => [p.name, p.description, ...(p.highlights ?? []), p.url].filter(Boolean).join(" — ")) : fallback?.projects ?? [],
  };
}
