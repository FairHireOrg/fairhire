import Link from "next/link";
import { ThemeToggle } from "./_shared/ThemeToggle";
import { EditorShot } from "./_landing/Shot";
import { LandingDrop } from "./_landing/LandingDrop";
import "./_landing/landing.css";

const PARSED = [
  ["Jordan Lee", ""],
  ["Backend Engineer", ""],
  ["jordan.lee@example.com", ""],
  ["San Francisco, CA", "Phone missing"],
  ["linkedin.com/in/jordanlee", ""],
  ["EXPERIENCE", ""],
  ["Senior Backend Engineer", ""],
  ["Northwind Health", ""],
  ["Data Engineer", ""],
  ["Jun 2019 – 12/2021", "Mixed date format"],
] as const;

export default function Home() {
  return (
    <div className="lp">
      <header className="lp-nav">
        <Link href="/" className="wordmark"><span className="wordmark-mark">F</span>FairHire</Link>
        <ThemeToggle />
      </header>

      <main>
        <section className="lp-hero" aria-labelledby="hero-h">
          <h1 id="hero-h" className="display">Write a resume every parser can read.</h1>
          <div className="lp-hero-body">
            <p className="lp-lede">
              Drop in a PDF, DOCX or plain text. See what a tracking system actually reads, fix it on the page,
              and export a clean file. Nothing to sign up for.
            </p>
            <LandingDrop />
          </div>
        </section>

        <section className="lp-band" aria-labelledby="ui-h">
          <h2 id="ui-h" className="display">A familiar interface</h2>
          <EditorShot />
        </section>

        <section className="lp-proof" aria-label="What the editor shows you">
          <figure className="lp-parsed" aria-label="The text a parser extracts, with two problem lines flagged">
            <div className="lp-parsed-head">
              <span>What parsers see</span>
              <span className="lp-seg" aria-hidden="true"><b>Original</b><i>Rebuilt</i></span>
            </div>
            <ol className="mono" aria-label="Text a parser extracts, with two lines flagged">
              {PARSED.map(([line, flag], i) => (
                <li key={i} className={flag ? "is-flag" : ""}>
                  <span className="ln" aria-hidden="true">{i + 1}</span>
                  <span className="lt">{line}</span>
                  {flag && <span className="lf">{flag}</span>}
                </li>
              ))}
            </ol>
          </figure>

          <figure className="lp-crop" aria-label="The same resume with the mixed date format pointed out on the line">
            <div className="lp-crop-page" aria-hidden="true">
              <p className="h">EXPERIENCE</p>
              <div className="row"><b>Senior Backend Engineer</b><span>Jan 2022 – Present</span></div>
              <p className="sub">Northwind Health</p>
              <div className="row mt"><b>Data Engineer</b><span className="flag">Jun 2019 – 12/2021</span></div>
              <p className="sub">Brightline Labs</p>
              <p className="note"><strong>Dates use mixed formats</strong><span>Use one format throughout.</span></p>
              <ul>
                <li>Built Airflow pipelines processing 40M claims records per day</li>
                <li>Cut warehouse query latency 62% by redesigning partition strategy</li>
                <li>Mentored three junior engineers through onboarding</li>
              </ul>
            </div>
          </figure>
        </section>
      </main>

      <footer className="lp-foot">
        <div className="lp-foot-top">
          <span className="wordmark"><span className="wordmark-mark">F</span>FairHire</span>
          <nav aria-label="Footer">
            <Link href="/editor">Editor</Link>
            <Link href="/editor?new=1">Start from a blank page</Link>
          </nav>
        </div>

      </footer>
    </div>
  );
}
