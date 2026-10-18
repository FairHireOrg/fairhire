import Link from "next/link";
import { ThemeToggle } from "./_shared/ThemeToggle";
import { Wordmark } from "./_shared/Wordmark";
import { EditorShot } from "./_landing/Shot";
import { LandingDrop } from "./_landing/LandingDrop";

type Line = readonly [text: string, flag?: string, severity?: "high" | "medium"];

// Mirrors DEMO_DOC and the titles of its checks in DEMO_SCORED (app/_lib/demo.ts).
const PARSED: readonly Line[] = [
  ["Jordan Lee"],
  ["Backend Engineer"],
  ["jordan.lee@example.com"],
  ["San Francisco, CA", "Phone number not found in text", "high"],
  ["linkedin.com/in/jordanlee"],
  ["SUMMARY"],
  ["Backend engineer with six years building…"],
  ["EXPERIENCE"],
  ["Senior Backend Engineer"],
  ["Northwind Health"],
  ["Data Engineer"],
  ["Jun 2019 – 12/2021", "Dates use mixed formats", "medium"],
];

const FLAG = {
  high: "bg-bad-soft text-bad shadow-[inset_3px_0_0_var(--bad)]",
  medium: "bg-warn-soft text-warn shadow-[inset_3px_0_0_var(--warn)]",
};

const WRAP = "mx-auto w-[min(1200px,100%-48px)]";

export default function Home() {
  return (
    <div className="min-h-dvh">
      <header className={`${WRAP} flex h-18 items-center justify-between border-b border-rule`}>
        <Wordmark href="/" />
        <ThemeToggle />
      </header>

      <main>
        <section className={`${WRAP} grid justify-items-center gap-9 pt-12 pb-22 min-[861px]:pt-18`} aria-labelledby="hero-h">
          <h1 id="hero-h" className="display w-[min(660px,100%)] text-[clamp(38px,5.4vw,60px)] leading-[1.04] text-balance text-center">Write a resume every ATS can read.</h1>
          <div className="grid w-[min(540px,100%)] gap-7">
            <p className="text-center text-lg/[1.6] text-ink-2">
              Drop in a PDF, DOCX, Markdown or plain text. See what a tracking system actually reads, fix it on the page,
              and export a clean file. Nothing to sign up for.
            </p>
            <LandingDrop />
          </div>
        </section>

        <section className={`${WRAP} grid justify-items-center gap-9 pt-2 pb-24`} aria-labelledby="ui-h">
          <h2 id="ui-h" className="display text-center text-[clamp(30px,3.8vw,42px)] leading-[1.1]">A familiar interface</h2>
          <EditorShot />
        </section>

        <section className={`${WRAP} grid grid-cols-1 items-start pb-28 min-[861px]:grid-cols-12`} aria-label="What the editor shows you">
          <figure className="relative z-1 m-0 min-[861px]:col-span-7 min-[861px]:col-start-1 min-[861px]:row-start-1 min-[861px]:mt-18" aria-label="The text a parser extracts, with two problem lines flagged">
            <div className="flex items-center justify-between gap-3 rounded-t-(--r-lg) border border-b-0 border-rule bg-surface px-5 py-3.5 text-sm font-semibold">
              <span>What parsers see</span>
              <span className="inline-flex gap-0.5 rounded-[9px] bg-sunken p-[3px] text-[13px]" aria-hidden="true">
                <b className="rounded-[7px] bg-surface px-3 py-[5px] shadow-[0_1px_2px_rgba(11,18,32,0.12)]">After cleanup</b>
                <i className="rounded-[7px] px-3 py-[5px] font-medium not-italic text-ink-2">As uploaded</i>
              </span>
            </div>
            <ol className="mono m-0 list-none rounded-b-(--r-lg) border border-rule bg-surface pt-2 pb-3 pl-0 text-sm leading-none" aria-label="Text a parser extracts, with two lines flagged">
              {PARSED.map(([line, flag, severity], i) => (
                <li key={i} className={`flex items-center gap-4 px-5 py-[9px] ${severity ? FLAG[severity] : ""}`}>
                  <span className="w-[1.6em] text-right text-ink-3" aria-hidden="true">{i + 1}</span>
                  <span>{line}</span>
                  {flag && <span className="ml-1 font-sans text-xs font-semibold">{flag}</span>}
                </li>
              ))}
            </ol>
          </figure>

          <figure className="relative z-2 m-0 mt-[-36px] ml-7 min-[861px]:col-span-7 min-[861px]:col-start-6 min-[861px]:row-start-1 min-[861px]:m-0" aria-label="The same resume with the mixed date format pointed out on the line">
            <div className="rounded-sm bg-page px-8 pt-7 pb-[30px] font-(family-name:--font-page) text-sm/[1.45] text-doc-ink shadow-(--shadow-pop)" aria-hidden="true">
              <p className="mb-3 border-b border-doc-ink pb-[3px] text-[11.5px] font-bold tracking-[0.09em]">EXPERIENCE</p>
              <div className="flex items-baseline justify-between gap-3"><b>Senior Backend Engineer</b><span className="text-[13px] text-doc-ink-2">Jan 2022 – Present</span></div>
              <p className="text-[13.5px] text-doc-ink-2">Northwind Health</p>
              <div className="mt-4 flex items-baseline justify-between gap-3"><b>Data Engineer</b><span className="rounded-[2px] bg-[#fff1dc] px-1 text-[13px] text-doc-ink-2 shadow-[inset_0_-2px_0_#b25e09]">Jun 2019 – 12/2021</span></div>
              <p className="text-[13.5px] text-doc-ink-2">Brightline Labs</p>
              <p className="my-3 ml-auto grid w-[min(260px,100%)] gap-px rounded-lg border-[1.5px] border-[#b25e09] bg-white px-3.5 py-2.5 font-sans shadow-[0_6px_16px_rgba(178,94,9,0.2)]">
                <strong className="text-[13.5px]">Dates use mixed formats</strong>
                <span className="text-[12.5px] text-[#364152]">Use one format throughout.</span>
              </p>
              <ul className="m-0 pl-[1.1em] text-[13.5px] *:mb-1">
                <li>Built Airflow pipelines processing 40M claims records per day</li>
                <li>Cut warehouse query latency 62% by redesigning partition strategy</li>
                <li>Mentored three junior engineers through onboarding</li>
              </ul>
            </div>
          </figure>
        </section>
      </main>

      <footer className={`${WRAP} flex items-center justify-between gap-4 border-t border-rule pt-7 pb-11 text-[13.5px] text-ink-3`}>
        <Wordmark className="text-ink" />
        <nav aria-label="Footer" className="flex gap-6 text-sm font-medium [&_a]:text-ink-2 [&_a]:no-underline [&_a:hover]:text-ink [&_a:hover]:underline [&_a:hover]:underline-offset-4">
          <Link href="/editor">Editor</Link>
          <Link href="/editor?new=1">Start from a blank page</Link>
        </nav>
      </footer>
    </div>
  );
}
