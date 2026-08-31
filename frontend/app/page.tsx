import Link from "next/link";

/* A small product-specific SVG: two mini panes joined by a real match line. */
function MatchVisual() {
  return (
    <svg
      viewBox="0 0 520 360"
      className="h-auto w-full"
      role="img"
      aria-label="A job-description requirement connected to a matching resume term"
    >
      <defs>
        <linearGradient id="paper" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#ffffff" />
          <stop offset="1" stopColor="#faf8f2" />
        </linearGradient>
      </defs>

      {/* JD pane */}
      <rect x="8" y="20" width="214" height="320" rx="10" fill="url(#paper)" stroke="#e4e0d4" />
      <text x="24" y="46" fontSize="10" letterSpacing="1.6" fill="#6f6a5b" fontFamily="ui-monospace,monospace">
        JOB DESCRIPTION
      </text>
      <rect x="24" y="66" width="120" height="7" rx="3.5" fill="#e4e0d4" />
      <rect x="24" y="82" width="88" height="7" rx="3.5" fill="#e4e0d4" />
      <text x="24" y="120" fontSize="10" letterSpacing="1.4" fill="#6f6a5b" fontFamily="ui-monospace,monospace">
        REQUIRED
      </text>
      <rect x="24" y="138" width="150" height="22" rx="5" fill="rgba(138,90,0,0.10)" />
      <text x="32" y="153" fontSize="10" fill="#8a5a00" fontFamily="ui-monospace,monospace">
        distributed systems
      </text>
      <rect x="24" y="170" width="140" height="22" rx="5" fill="rgba(138,90,0,0.10)" />
      <text x="32" y="185" fontSize="10" fill="#8a5a00" fontFamily="ui-monospace,monospace">
        PostgreSQL
      </text>
      <rect x="24" y="202" width="150" height="22" rx="5" fill="rgba(35,116,63,0.12)" />
      <text x="32" y="217" fontSize="10" fill="#23743f" fontFamily="ui-monospace,monospace">
        Rest APIs
      </text>

      {/* Resume pane */}
      <rect x="298" y="20" width="214" height="320" rx="10" fill="url(#paper)" stroke="#e4e0d4" />
      <text x="314" y="46" fontSize="10" letterSpacing="1.6" fill="#6f6a5b" fontFamily="ui-monospace,monospace">
        RESUME
      </text>
      <rect x="314" y="140" width="150" height="22" rx="5" fill="rgba(35,116,63,0.12)" />
      <text x="322" y="155" fontSize="10" fill="#2e7d4f" fontFamily="ui-monospace,monospace">
        distributed + systems
      </text>
      <rect x="314" y="172" width="140" height="22" rx="5" fill="rgba(138,90,0,0.10)" />
      <text x="322" y="187" fontSize="10" fill="#8a5a00" fontFamily="ui-monospace,monospace">
        PostgreSQL
      </text>
      <rect x="314" y="204" width="150" height="22" rx="5" fill="rgba(35,116,63,0.12)" />
      <text x="322" y="219" fontSize="10" fill="#2e7d4f" fontFamily="ui-monospace,monospace">
        RESTful APIs
      </text>

      {/* Match lines */}
      <g fill="none" strokeLinecap="round">
        <path d="M 174 149 C 240 149, 272 151, 314 151" stroke="#8a5a00" strokeWidth="2" opacity="0.85" />
        <path d="M 174 181 C 240 181, 272 183, 314 183" stroke="#8a5a00" strokeWidth="2" opacity="0.85" />
        <path d="M 174 213 C 240 213, 272 215, 314 215" stroke="#2e7d4f" strokeWidth="2" opacity="0.85" />
      </g>
      <circle cx="314" cy="151" r="3.5" fill="#8a5a00" />
      <circle cx="314" cy="183" r="3.5" fill="#8a5a00" />
      <circle cx="314" cy="215" r="3.5" fill="#2e7d4f" />
    </svg>
  );
}

const PIPELINE = [
  {
    n: "01",
    name: "Parse",
    mono: "regex + curated ontology",
    body: "Email, phone, dates, degrees and headings are extracted by deterministic rules. Every skill is tagged with exact character offsets.",
  },
  {
    n: "02",
    name: "Extract",
    mono: "optional DeepSeek · never a decider",
    body: "With a key set, soft skills, degrees, years and generic abilities are lifted out of the JD. Without one, it runs on the ontology alone.",
  },
  {
    n: "03",
    name: "Match",
    mono: "exact · contextual · family",
    body: "Each requirement is resolved with a fixed rule — no near-match tier — and drawn as a line between the panes. Same input, same score.",
  },
];

const GUARANTEES = [
  {
    k: "Deterministic",
    v: "The score is a fixed rule over confirmed matches. The LLM only *suggests* whether a requirement is met (with a quoted resume span); you confirm it, so the exact same inputs and answers always give the same grade.",
  },
  {
    k: "Explainable",
    v: "Every point traces to a concrete rule or a quoted piece of resume evidence, and every connecting line is a real matched requirement with a quality label.",
  },
  {
    k: "Bias-aware by design",
    v: "Lexical matching is word-boundary and rule-based. Semantic inference is a single, quoted, human-readable suggestion — never a hidden similarity model.",
  },
];

export default function Landing() {
  return (
    <div className="min-h-dvh bg-base text-ink">
      <header className="sticky top-0 z-20 border-b border-line bg-base/85 backdrop-blur-sm">
        <div className="mx-auto flex h-14 w-full max-w-[1120px] items-center justify-between px-5">
          <div className="flex items-center gap-2.5">
            <span className="h-1.5 w-1.5 rounded-full bg-accent" aria-hidden />
            <span className="font-mono text-sm font-semibold tracking-[0.22em] text-ink">FAIRHIRE</span>
          </div>
          <nav className="flex items-center gap-6 font-mono text-[11px] uppercase tracking-[0.14em] text-muted">
            <a href="#how" className="hidden transition hover:text-ink sm:block">
              How it works
            </a>
            <Link
              href="/app"
              className="rounded-md bg-accent px-3.5 py-1.5 text-accent-ink transition hover:brightness-110"
            >
              Open app
            </Link>
          </nav>
        </div>
      </header>

      {/* Hero */}
      <section className="border-b border-line">
        <div className="mx-auto grid w-full max-w-[1120px] gap-10 px-5 pb-16 pt-16 sm:pt-20 lg:grid-cols-2 lg:items-center lg:gap-14">
          <div>
            <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-accent">
              Deterministic resume ↔ job-description matching
            </p>
            <h1 className="mt-4 text-4xl font-semibold leading-[1.05] tracking-tight text-ink sm:text-5xl lg:text-6xl">
              Know exactly why a
              <br className="hidden sm:block" /> resume fits.
            </h1>
            <p className="mt-5 max-w-[52ch] text-lg leading-relaxed text-muted">
              Paste a job description and a resume. FairHire extracts the real requirements and
              matches them with fixed rules — drawing a line for every term that truly matches, in
              a score you can trace back to a rule.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Link
                href="/app"
                className="rounded-md bg-accent px-6 py-3 font-mono text-xs font-semibold uppercase tracking-[0.16em] text-accent-ink transition hover:brightness-110 active:scale-[0.99]"
              >
                Score a match
              </Link>
              <a
                href="#how"
                className="rounded-md border border-line bg-panel px-6 py-3 font-mono text-xs font-semibold uppercase tracking-[0.16em] text-ink transition hover:border-line-strong"
              >
                How it works
              </a>
            </div>
            <dl className="mt-10 grid max-w-md grid-cols-3 gap-6 border-t border-line pt-6">
              <div>
                <dt className="font-mono text-2xl font-medium tabular-nums text-ink">0</dt>
                <dd className="mt-1 font-mono text-[10px] uppercase tracking-[0.12em] text-faint">
                  LLMs in the verdict
                </dd>
              </div>
              <div>
                <dt className="font-mono text-2xl font-medium tabular-nums text-ink">100%</dt>
                <dd className="mt-1 font-mono text-[10px] uppercase tracking-[0.12em] text-faint">
                  repeatable
                </dd>
              </div>
              <div>
                <dt className="font-mono text-2xl font-medium tabular-nums text-ink">3</dt>
                <dd className="mt-1 font-mono text-[10px] uppercase tracking-[0.12em] text-faint">
                  match tiers
                </dd>
              </div>
            </dl>
          </div>

          <div className="relative">
            <div
              className="pointer-events-none absolute -inset-6 -z-10 rounded-3xl"
              style={{
                backgroundImage:
                  "repeating-linear-gradient(90deg, transparent 0 39px, rgba(138,90,0,0.06) 39px 40px)",
              }}
              aria-hidden
            />
            <div className="rounded-xl border border-line bg-panel p-5 shadow-[0_30px_60px_-30px_rgba(27,26,22,0.25)]">
              <MatchVisual />
            </div>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="scroll-mt-20 border-b border-line">
        <div className="mx-auto w-full max-w-[1120px] px-5 py-20">
          <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-accent">The pipeline</p>
          <h2 className="mt-3 max-w-[26ch] text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
            Three deterministic stages. No black box.
          </h2>

          <div className="mt-12 grid gap-px overflow-hidden rounded-xl border border-line bg-line lg:grid-cols-3">
            {PIPELINE.map((p) => (
              <div key={p.n} className="flex flex-col bg-panel p-7">
                <div className="flex items-baseline justify-between">
                  <span className="font-mono text-xs text-faint">{p.n}</span>
                  <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted">
                    {p.mono}
                  </span>
                </div>
                <h3 className="mt-4 text-xl font-semibold text-ink">{p.name}</h3>
                <p className="mt-2 max-w-[38ch] text-sm leading-relaxed text-muted">{p.body}</p>
              </div>
            ))}
          </div>

          <div className="mt-6 rounded-xl border border-line bg-panel-2 p-6 sm:p-8">
            <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-faint">
              A match must be real
            </p>
            <div className="mt-4 grid gap-6 md:grid-cols-3">
              {GUARANTEES.map((g) => (
                <div key={g.k}>
                  <h3 className="flex items-center gap-2 text-sm font-semibold text-ink">
                    <span className="h-1.5 w-1.5 rounded-full bg-accent" aria-hidden />
                    {g.k}
                  </h3>
                  <p className="mt-1.5 text-[13px] leading-relaxed text-muted">{g.v}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Determinism showcase */}
      <section className="border-b border-line">
        <div className="mx-auto grid w-full max-w-[1120px] gap-10 px-5 py-20 lg:grid-cols-[minmax(0,1fr)_minmax(0,0.9fr)] lg:items-center">
          <div>
            <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-accent">
              Rule-first scoring
            </p>
            <h2 className="mt-3 max-w-[24ch] text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
              A scorecard you can interrogate.
            </h2>
            <ul className="mt-6 space-y-3">
              {[
                "Required-vs-nice-to-have split from where a term sits in the JD",
                "Exact family relations (SQL → PostgreSQL) — never fuzzy similarity",
                "Lexical tiers first; the LLM only infers the leftovers, quoting its evidence",
                "Blockers that tell you what to add, not just a number",
              ].map((li) => (
                <li key={li} className="flex gap-3 text-[15px] leading-relaxed text-muted">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-ok" aria-hidden />
                  {li}
                </li>
              ))}
            </ul>
          </div>

          <div className="rounded-xl border border-line bg-panel p-5 font-mono text-[12px] leading-relaxed">
            <div className="flex items-center gap-2 border-b border-line pb-3">
              <span className="h-2 w-2 rounded-full bg-warn/70" aria-hidden />
              <span className="h-2 w-2 rounded-full bg-accent/70" aria-hidden />
              <span className="h-2 w-2 rounded-full bg-ok/70" aria-hidden />
              <span className="ml-2 text-[10px] uppercase tracking-[0.16em] text-faint">
                rule · example
              </span>
            </div>
            <p className="pt-4 text-muted">$ JD requires “SQL”</p>
            <p className="text-ink">→ resume has PostgreSQL</p>
            <p className="text-ok">✓ family: SQL ⊃ PostgreSQL</p>
            <p className="pt-3 text-muted">$ JD requires “JavaScript”</p>
            <p className="text-ink">→ resume shows TypeScript</p>
            <p className="text-ok">✓ llm: “TypeScript is a superset of JavaScript”</p>
            <p className="pt-3 text-muted">
              lexical relations are deterministic rules; only what they can’t resolve
              falls through to a quoted, human-readable LLM judgement — never a hidden score.
            </p>
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="mx-auto w-full max-w-[1120px] px-5 py-20">
        <div className="rounded-2xl border border-line bg-panel px-6 py-12 text-center sm:px-12">
          <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-accent">
            Ready to read a resume
          </p>
          <h2 className="mx-auto mt-3 max-w-[22ch] text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
            Deterministic, explainable, reproducible.
          </h2>
          <p className="mx-auto mt-4 max-w-[52ch] text-[15px] leading-relaxed text-muted">
            Drop in a JD and a candidate and get an instant score with the lines drawn — same
            answer every time.
          </p>
          <Link
            href="/app"
            className="mt-8 inline-block rounded-md bg-accent px-8 py-3.5 font-mono text-xs font-semibold uppercase tracking-[0.16em] text-accent-ink transition hover:brightness-110 active:scale-[0.99]"
          >
            Go to app
          </Link>
        </div>
      </section>

      <footer className="border-t border-line">
        <div className="mx-auto flex w-full max-w-[1120px] flex-col gap-2 px-5 py-6 font-mono text-[11px] tracking-[0.04em] text-faint sm:flex-row sm:items-center sm:justify-between">
          <span>© {new Date().getFullYear()} FairHire. All rights reserved.</span>
          <span>Deterministic resume ↔ job-description matching</span>
        </div>
      </footer>
    </div>
  );
}
