"use client";

import { useEffect, useMemo, useState } from "react";
import { UploadSimple } from "@phosphor-icons/react";
import { analyzeFitness, checkHealth, type FitnessResult } from "../lib/api";
import MatchMap from "../components/MatchMap";

const STEPS = [
  {
    n: "01",
    title: "Parse",
    body: "Regex rules pull out emails, phones, dates, degrees and section headings. A curated skill ontology tags every language, framework and tool with exact character offsets.",
  },
  {
    n: "02",
    title: "Extract",
    body: "With a DeepSeek key set, soft skills, degrees, years and generic abilities are pulled from the JD. Without a key, the system runs on the ontology alone.",
  },
  {
    n: "03",
    title: "Match",
    body: "Every requirement is checked against the resume with exact rules and drawn as an SVG line between the two panes. Same input, same score, every time.",
  },
];

function DimensionRow({
  score,
  label,
  detail,
}: {
  score: number;
  label: string;
  detail: string;
}) {
  const pct = Math.max(0, Math.min(100, score));
  return (
    <div className="flex items-center gap-5 py-3">
      <div className="min-w-0 flex-1">
        <span className="text-sm font-medium text-ink">{label}</span>
        {detail ? (
          <p className="mt-0.5 line-clamp-2 text-xs leading-snug text-faint">{detail}</p>
        ) : null}
      </div>
      <div className="w-32 shrink-0">
        <div className="h-1 overflow-hidden rounded-full bg-inset">
          <div
            className="h-full rounded-full bg-accent transition-[width] duration-500"
            style={{ width: `${pct}%` }}
          />
        </div>
        <div className="mt-1 text-right font-mono text-sm tabular-nums text-ink">
          {score.toFixed(0)}
        </div>
      </div>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string | string[] | null | undefined }) {
  if (!value || (Array.isArray(value) && value.length === 0)) return null;
  return (
    <div>
      <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-faint">{label}</p>
      <p className="mt-0.5 break-all text-sm text-muted">
        {Array.isArray(value) ? value.join(" · ") : value}
      </p>
    </div>
  );
}

function Chip({ tone = "neutral", children }: { tone?: "neutral" | "ok" | "warn"; children: React.ReactNode }) {
  const cls =
    tone === "ok"
      ? "bg-ok/10 text-ok"
      : tone === "warn"
        ? "bg-warn/10 text-warn"
        : "border border-line bg-inset text-muted";
  return (
    <span className={`rounded-sm px-2 py-1 font-mono text-[11px] ${cls}`}>{children}</span>
  );
}

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [resumeText, setResumeText] = useState("");
  const [jobDescription, setJobDescription] = useState("");
  const [result, setResult] = useState<FitnessResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [apiOk, setApiOk] = useState<boolean | null>(null);

  useEffect(() => {
    checkHealth()
      .then(() => setApiOk(true))
      .catch(() => setApiOk(false));
  }, []);

  const canAnalyze = useMemo(() => {
    const hasResume = Boolean(file) || resumeText.trim().length > 20;
    return hasResume && jobDescription.trim().length > 20 && !loading;
  }, [file, resumeText, jobDescription, loading]);

  async function onAnalyze() {
    setError(null);
    setLoading(true);
    try {
      const data = await analyzeFitness({
        jobDescription,
        file,
        resumeText: file ? undefined : resumeText,
      });
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analyze failed");
    } finally {
      setLoading(false);
    }
  }

  const present = result?.required_terms.filter((t) => t.matched) ?? [];
  const missing = result?.required_terms.filter((t) => !t.matched) ?? [];

  return (
    <div className="flex min-h-dvh flex-col bg-base text-ink">
      <header className="sticky top-0 z-20 border-b border-line bg-base/90 backdrop-blur-sm">
        <div className="mx-auto flex h-14 w-full max-w-[1100px] items-center justify-between px-5">
          <div className="flex items-center gap-2.5">
            <span className="h-1.5 w-1.5 rounded-full bg-accent" aria-hidden />
            <span className="font-mono text-sm font-semibold tracking-[0.22em] text-ink">
              FAIRHIRE
            </span>
          </div>
          <div className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.14em] text-muted">
            <span
              className={`h-2 w-2 rounded-full ${
                apiOk ? "bg-ok" : apiOk === false ? "bg-warn" : "bg-faint pulse-dot"
              }`}
              aria-hidden
            />
            <span>
              api ·{" "}
              {apiOk === null ? (
                "checking"
              ) : apiOk ? (
                <span className="text-ok">online</span>
              ) : (
                <span className="text-warn">offline</span>
              )}
            </span>
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-[1100px] flex-1 px-5 pb-16">
        <section className="grid gap-5 pt-8 sm:gap-6 lg:grid-cols-2 lg:pt-12">
          <div className="flex flex-col overflow-hidden rounded-md border border-line bg-panel">
            <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-2.5">
              <h2 className="font-mono text-[11px] font-semibold uppercase tracking-[0.18em] text-ink">
                Job description
              </h2>
              <span className="font-mono text-[11px] tabular-nums text-faint">
                {jobDescription.length} chars
              </span>
            </div>
            <textarea
              value={jobDescription}
              onChange={(e) => setJobDescription(e.target.value)}
              placeholder="Paste the full JD here…"
              rows={18}
              className="w-full flex-1 resize-y bg-transparent px-4 py-3 text-sm leading-relaxed text-ink outline-none placeholder:text-faint"
            />
          </div>

          <div className="flex flex-col overflow-hidden rounded-md border border-line bg-panel">
            <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-2.5">
              <h2 className="font-mono text-[11px] font-semibold uppercase tracking-[0.18em] text-ink">
                Resume
              </h2>
              <span className="font-mono text-[11px] tabular-nums text-faint">
                {resumeText.length} chars
              </span>
            </div>

            <div className="px-4 pt-4">
              <label className="group flex cursor-pointer items-center gap-3 rounded-md border border-dashed border-line-strong bg-inset px-3 py-2.5 transition-colors hover:border-accent">
                <UploadSimple className="h-4 w-4 shrink-0 text-accent" weight="duotone" />
                <span className="truncate font-mono text-xs text-muted group-hover:text-ink">
                  {file ? file.name : "Upload .pdf · .txt · .md"}
                </span>
                <input
                  type="file"
                  accept=".pdf,.txt,.md,application/pdf,text/plain"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                  className="sr-only"
                />
              </label>
            </div>

            <textarea
              value={resumeText}
              onChange={(e) => setResumeText(e.target.value)}
              placeholder="Or paste resume text here…"
              rows={12}
              className="mt-3 w-full flex-1 resize-y bg-transparent px-4 py-1 text-sm leading-relaxed text-ink outline-none placeholder:text-faint"
            />

            <div className="border-t border-line p-4">
              <button
                type="button"
                disabled={!canAnalyze}
                onClick={onAnalyze}
                className="flex w-full items-center justify-center gap-2 rounded-md bg-accent px-5 py-2.5 font-mono text-xs font-semibold uppercase tracking-[0.18em] text-accent-ink transition hover:brightness-110 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-35"
              >
                {loading ? (
                  <>
                    <span className="h-1.5 w-1.5 rounded-full bg-accent-ink pulse-dot" aria-hidden />
                    Scoring…
                  </>
                ) : (
                  "Score match"
                )}
              </button>
              {!canAnalyze && !loading && !error ? (
                <p className="mt-3 text-center font-mono text-[11px] text-faint">
                  needs 20+ chars of JD and resume
                </p>
              ) : null}
              {error ? (
                <p className="mt-3 rounded-md border border-warn/30 bg-warn/10 px-3 py-2 font-mono text-xs text-warn">
                  {error}
                </p>
              ) : null}
            </div>
          </div>
        </section>

        {result ? (
          <section className="fade-up mt-8 space-y-5">
            <div className="grid overflow-hidden rounded-md border border-line bg-panel md:grid-cols-[minmax(0,1fr)_minmax(0,1.35fr)]">
              <div className="flex flex-col justify-center border-b border-line px-6 py-6 md:border-b-0 md:border-r md:px-8 md:py-8">
                <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-faint">
                  Overall score
                </p>
                <p className="mt-3 font-mono text-6xl font-medium tabular-nums leading-none tracking-tight text-ink md:text-7xl">
                  {result.overall_score.toFixed(1)}
                </p>
                <div className="mt-5 flex flex-wrap gap-2">
                  {result.job_title ? (
                    <Chip>role · {result.job_title}</Chip>
                  ) : null}
                  <Chip>extraction · {result.extraction_mode}</Chip>
                  <Chip tone="ok">
                    {present.length}/{result.required_terms.length} required present
                  </Chip>
                  <Chip tone="warn">{missing.length} missing</Chip>
                </div>
              </div>

              <div className="px-6 py-6 md:px-8 md:py-8">
                <div className="divide-y divide-line">
                  {result.dimensions.map((d) => (
                    <DimensionRow
                      key={d.key}
                      score={d.score}
                      label={d.label}
                      detail={d.detail}
                    />
                  ))}
                </div>
              </div>
            </div>

            <div className="grid gap-5 lg:grid-cols-2">
              <div className="overflow-hidden rounded-md border border-line bg-panel">
                <div className="border-b border-line px-4 py-2.5">
                  <h3 className="font-mono text-[11px] font-semibold uppercase tracking-[0.18em] text-ink">
                    Blockers
                  </h3>
                </div>
                {result.blockers.length === 0 ? (
                  <p className="px-4 py-5 font-mono text-xs text-muted">No blockers detected.</p>
                ) : (
                  <ul className="divide-y divide-line">
                    {result.blockers.map((b) => (
                      <li key={b.code + b.message} className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-warn">
                            {b.severity}
                          </span>
                          <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-faint">
                            {b.code}
                          </span>
                        </div>
                        <p className="mt-1 text-sm font-medium text-ink">{b.message}</p>
                        <p className="mt-0.5 text-[13px] leading-relaxed text-muted">
                          {b.suggestion}
                        </p>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div className="overflow-hidden rounded-md border border-line bg-panel">
                <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-2.5">
                  <h3 className="font-mono text-[11px] font-semibold uppercase tracking-[0.18em] text-ink">
                    Required skills
                  </h3>
                  <span className="font-mono text-[11px] tabular-nums text-faint">
                    {present.length}/{result.required_terms.length} present
                  </span>
                </div>
                <ul className="divide-y divide-line">
                  {result.required_terms.slice(0, 18).map((t) => (
                    <li key={t.term} className="flex items-center justify-between gap-3 px-4 py-2">
                      <span className="flex min-w-0 items-center gap-2">
                        <span className="rounded-sm bg-inset px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-[0.1em] text-muted">
                          {t.kind}
                        </span>
                        <span className="truncate text-sm text-ink">{t.term}</span>
                      </span>
                      <span
                        className={
                          t.matched
                            ? "shrink-0 font-mono text-[11px] tabular-nums text-ok"
                            : "shrink-0 font-mono text-[11px] tabular-nums text-warn"
                        }
                      >
                        {t.matched ? `matched${t.quality ? ` · ${t.quality}` : ""}` : "missing"}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            <div className="overflow-hidden rounded-md border border-line bg-panel">
              <div className="border-b border-line px-4 py-2.5">
                <h3 className="font-mono text-[11px] font-semibold uppercase tracking-[0.18em] text-ink">
                  Extracted fields
                </h3>
              </div>
              <div className="grid grid-cols-1 gap-x-8 gap-y-4 px-5 py-4 sm:grid-cols-2 lg:grid-cols-4">
                <Field label="Email" value={result.resume_features?.email} />
                <Field label="Phone" value={result.resume_features?.phone} />
                <Field label="Location" value={result.resume_features?.location} />
                <Field label="LinkedIn" value={result.resume_features?.linkedin} />
                <Field label="GitHub" value={result.resume_features?.github} />
                <Field label="Degrees" value={result.resume_features?.degrees} />
                <Field label="Role titles" value={result.resume_titles} />
              </div>
            </div>

            <div className="overflow-hidden rounded-md border border-line bg-panel">
              <MatchMap result={result} />
            </div>

            <p className="font-mono text-[11px] leading-relaxed text-faint">
              {result.disclaimer}
            </p>
          </section>
        ) : null}

        <section className="mt-8 grid gap-px overflow-hidden rounded-md border border-line bg-line sm:grid-cols-3">
          {STEPS.map((s) => (
            <div key={s.n} className="bg-base p-5">
              <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-accent">
                {s.n}
              </p>
              <h3 className="mt-2 text-sm font-semibold text-ink">{s.title}</h3>
              <p className="mt-1.5 text-[13px] leading-relaxed text-muted">{s.body}</p>
            </div>
          ))}
        </section>

        <section className="mt-5 rounded-md border border-line bg-panel px-5 py-4 sm:mt-6">
          <p className="max-w-[70ch] text-sm leading-relaxed text-muted">
            Matches are computed with fixed rules, so the same resume and JD always produce the
            same score and the same links. With a DeepSeek key set, extraction is added for soft
            skills, degrees, and years — it still never decides whether a match exists.
          </p>
        </section>
      </main>

      <footer className="border-t border-line">
        <div className="mx-auto flex w-full max-w-[1100px] flex-col gap-2 px-5 py-6 font-mono text-[11px] tracking-[0.04em] text-faint sm:flex-row sm:items-center sm:justify-between">
          <span>FairHire · deterministic resume ↔ job-description matching</span>
          <span>regex + skill ontology · optional DeepSeek extraction</span>
        </div>
      </footer>
    </div>
  );
}
