"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const STORAGE_KEY = "fairhire_onboarded";

type Step = {
  target: string;
  eyebrow: string;
  title: string;
  body: string;
};

const STEPS: Step[] = [
  {
    target: "jd",
    eyebrow: "Step 1 · Input",
    title: "Paste the job description",
    body: "Drop the full JD in the left pane — requirements, responsibilities and preferred quals all go here.",
  },
  {
    target: "resume",
    eyebrow: "Step 2 · Input",
    title: "Upload or paste a resume",
    body: "Add the candidate's resume on the right. Upload a PDF, or paste plain text — the parser handles both.",
  },
  {
    target: "submit",
    eyebrow: "Step 3 · Score",
    title: "Run the match",
    body: "Hit \u201cScore match\u201d to get an instant, explainable verdict — every line drawn is a real matching requirement.",
  },
];

function measure(el: HTMLElement | null): DOMRect | null {
  return el ? el.getBoundingClientRect() : null;
}

export default function Onboarding() {
  const [index, setIndex] = useState(-1);
  const [done, setDone] = useState(false);
  const [rect, setRect] = useState<DOMRect | null>(null);
  const elRef = useRef<HTMLElement | null>(null);

  const targetId = index >= 0 ? STEPS[index].target : null;

  const update = useCallback(() => {
    if (!targetId) return;
    const el = document.querySelector<HTMLElement>(`[data-tour="${targetId}"]`);
    elRef.current = el;
    setRect(measure(el));
  }, [targetId]);

  // Kick off on mount / first target: read preference, then measure. Deferred
  // to a rAF so the writes are not synchronous within the effect body.
  useEffect(() => {
    const raf = requestAnimationFrame(() => {
      if (typeof window === "undefined") return;
      try {
        if (localStorage.getItem(STORAGE_KEY)) {
          setDone(true);
          return;
        }
      } catch {
        /* ignore storage failures (private mode) */
      }
      setIndex(0);
      if (document.querySelector(`[data-tour="${STEPS[0].target}"]`)) update();
    });
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Re-measure on resize/scroll and when the target changes.
  useEffect(() => {
    if (!targetId) return;
    const raf = requestAnimationFrame(() => update());
    window.addEventListener("resize", update);
    window.addEventListener("scroll", update, true);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", update);
      window.removeEventListener("scroll", update, true);
    };
  }, [targetId, update]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") finish();
      if (e.key === "ArrowRight") next();
      if (e.key === "ArrowLeft") prev();
    };
    if (index >= 0) window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [index]);

  function finish() {
    try {
      localStorage.setItem(STORAGE_KEY, "1");
    } catch {
      /* ignore storage failures (private mode) */
    }
    setDone(true);
    setIndex(-1);
  }

  const next = () => {
    if (index >= STEPS.length - 1) finish();
    else setIndex((i) => i + 1);
  };
  const prev = () => setIndex((i) => Math.max(0, i - 1));

  if (done || index < 0) return null;

  const step = STEPS[index];
  const offset = 4;
  const top = rect ? rect.top - offset : 0;
  const left = rect ? rect.left - offset : 0;
  const width = rect ? rect.width + offset * 2 : 0;
  const height = rect ? rect.height + offset * 2 : 0;

  const tooltipW = 336;
  const gap = 14;
  const padding = 20;
  const bottomSpace = window.innerHeight - (rect ? rect.bottom : 0);
  const above = bottomSpace < 220 && (rect?.top ?? 0) > 220;
  const tipTop = above
    ? Math.max(padding, (rect?.top ?? 0) - gap)
    : Math.min(window.innerHeight - 220, (rect?.bottom ?? 0) + gap);
  const tipLeft = Math.max(
    padding,
    Math.min(window.innerWidth - tooltipW - padding, (rect?.left ?? padding) - 12),
  );
  const tipStyle: React.CSSProperties = {
    width: tooltipW,
    left: tipLeft,
    top: above ? tipTop - 220 : tipTop,
  };

  return (
    <div className="fixed inset-0 z-50" role="dialog" aria-modal="true" aria-label="Guided tour">
      {/* Spotlight: dims everything outside the target */}
      <div
        className="absolute rounded-lg transition-[top,left,width,height] duration-300 ease-out"
        style={{
          top,
          left,
          width,
          height,
          boxShadow: "0 0 0 9999px rgba(27,26,22,0.55)",
        }}
        aria-hidden
      />
      <div
        className="pointer-events-none absolute rounded-lg border-2 border-accent"
        style={{ top, left, width, height }}
        aria-hidden
      />

      {/* Tooltip */}
      <div
        className="fixed rounded-lg border border-line bg-panel shadow-2xl"
        style={tipStyle}
      >
        <div className="border-b border-line px-5 py-3">
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-accent">
            {step.eyebrow}
          </p>
          <h2 className="mt-1 text-base font-semibold text-ink">{step.title}</h2>
        </div>
        <p className="px-5 py-4 text-sm leading-relaxed text-muted">{step.body}</p>
        <div className="flex items-center justify-between gap-3 px-5 pb-4">
          <button
            type="button"
            onClick={finish}
            className="font-mono text-[11px] text-faint hover:text-ink"
          >
            Skip
          </button>
          <div className="flex items-center gap-2">
            <span className="font-mono text-[11px] tabular-nums text-faint">
              {index + 1} / {STEPS.length}
            </span>
            <button
              type="button"
              onClick={prev}
              disabled={index === 0}
              className="rounded-md border border-line bg-inset px-3 py-1.5 font-mono text-[11px] text-muted transition hover:text-ink disabled:opacity-40"
            >
              Back
            </button>
            <button
              type="button"
              onClick={next}
              className="rounded-md bg-accent px-3 py-1.5 font-mono text-[11px] font-semibold text-accent-ink transition hover:brightness-110"
            >
              {index === STEPS.length - 1 ? "Done" : "Next"}
            </button>
          </div>
        </div>
      </div>

      {/* Progress dots */}
      <div className="fixed inset-x-0 bottom-6 flex justify-center gap-2" aria-hidden>
        {STEPS.map((_, i) => (
          <span
            key={i}
            className={`h-1.5 rounded-full transition-all duration-300 ${
              i === index ? "w-5 bg-accent" : "w-1.5 bg-line-strong"
            }`}
          />
        ))}
      </div>
    </div>
  );
}
