"use client";

import { useLayoutEffect, useMemo, useRef, useState } from "react";
import type { FitnessResult, MatchLink } from "../lib/api";

const COLORS = [
  "#7fd6c7",
  "#8ab0ff",
  "#c79bff",
  "#ff9cb4",
  "#ffab6b",
  "#9fdc8a",
  "#7fd6ea",
  "#f09ad0",
];

const MARK_INK = "#1b1a16";
const PANEL = "#ffffff";

function colorFor(term: string): string {
  let h = 0;
  for (let i = 0; i < term.length; i++) h = (h * 31 + term.charCodeAt(i)) >>> 0;
  return COLORS[h % COLORS.length];
}

const QUALITY_LABEL: Record<MatchLink["quality"], string> = {
  exact: "exact match",
  contains: "contextual",
  family: "family match",
  inferred: "inferred (superset)",
  fuzzy: "near match",
};

/*
 * The backend no longer emits the `fuzzy` tier — a match only exists when a
 * term truly appears, holds as a deterministic family relation, or is entailed
 * by a curated superset. The key is kept here for API/type compatibility.
 */

type Line = {
  linkIdx: number;
  canonical: string;
  color: string;
  from: { x: number; y: number };
  to: { x: number; y: number };
};

function HighlightedText({
  text,
  sentenceStart,
  spans,
  side,
  hoverIdx,
  onHover,
}: {
  text: string;
  sentenceStart: number;
  spans: { start: number; end: number; linkIdx: number; color: string }[];
  side: "jd" | "resume";
  hoverIdx: number | null;
  onHover: (idx: number | null) => void;
}) {
  const sorted = [...spans]
    .map((s) => ({
      start: Math.max(0, s.start - sentenceStart),
      end: Math.min(text.length, s.end - sentenceStart),
      linkIdx: s.linkIdx,
      color: s.color,
    }))
    .filter((s) => s.end > s.start)
    .sort((a, b) => a.start - b.start);
  const merged = sorted.reduce<{ start: number; end: number; linkIdx: number; color: string }[]>(
    (acc, s) => {
      const last = acc[acc.length - 1];
      if (last && s.start <= last.end) {
        if (s.end > last.end) last.end = s.end;
        return acc;
      }
      acc.push({ ...s });
      return acc;
    },
    []
  );

  const segments: { text: string; isMatch: boolean; linkIdx?: number; color?: string }[] = [];
  let cursor = 0;
  for (const m of merged) {
    if (m.start > cursor) segments.push({ text: text.slice(cursor, m.start), isMatch: false });
    segments.push({
      text: text.slice(m.start, m.end),
      isMatch: true,
      linkIdx: m.linkIdx,
      color: m.color,
    });
    cursor = m.end;
  }
  if (cursor < text.length) segments.push({ text: text.slice(cursor), isMatch: false });

  return (
    <>
      {segments.map((seg, i) =>
        seg.isMatch ? (
          <mark
            key={`${side}-${seg.linkIdx}-${i}`}
            data-anchor={`${side}-${seg.linkIdx}`}
            data-link-idx={seg.linkIdx}
            onMouseEnter={() => onHover(seg.linkIdx!)}
            onMouseLeave={() => onHover(null)}
            className="cursor-pointer rounded-sm px-0.5 py-px font-medium transition-opacity"
            style={{
              backgroundColor: seg.color,
              color: MARK_INK,
              opacity: hoverIdx === null || hoverIdx === seg.linkIdx ? 1 : 0.15,
            }}
          >
            {seg.text}
          </mark>
        ) : (
          <span key={i} className="whitespace-pre-wrap">
            {seg.text}
          </span>
        )
      )}
    </>
  );
}

export default function MatchMap({ result }: { result: FitnessResult }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [showLines, setShowLines] = useState(true);
  const [requiredOnly, setRequiredOnly] = useState(false);
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);
  const [lines, setLines] = useState<Line[]>([]);

  const { jd_sentences, resume_sentences, links } = result;

  const displayedLinks = useMemo(
    () => links.filter((l) => !requiredOnly || l.required),
    [links, requiredOnly]
  );

  useLayoutEffect(() => {
    const container = containerRef.current;
    if (!container || !showLines || displayedLinks.length === 0) {
      setLines([]);
      return;
    }
    const compute = () => {
      const cRect = container.getBoundingClientRect();
      const next: Line[] = [];
      for (const link of displayedLinks) {
        const jdIdx = links.indexOf(link);
        const jEl = container.querySelector<HTMLElement>(`[data-anchor="jd-${jdIdx}"]`);
        const rEl = container.querySelector<HTMLElement>(`[data-anchor="resume-${jdIdx}"]`);
        if (!jEl || !rEl) continue;
        const jr = jEl.getBoundingClientRect();
        const rr = rEl.getBoundingClientRect();
        next.push({
          linkIdx: jdIdx,
          canonical: link.canonical,
          color: colorFor(link.canonical),
          from: { x: jr.right - cRect.left, y: jr.top + jr.height / 2 - cRect.top },
          to: { x: rr.left - cRect.left, y: rr.top + rr.height / 2 - cRect.top },
        });
      }
      setLines(next);
    };
    compute();
    const onResize = () => requestAnimationFrame(compute);
    window.addEventListener("resize", onResize);
    const t = setTimeout(onResize, 60);
    return () => {
      window.removeEventListener("resize", onResize);
      clearTimeout(t);
    };
  }, [displayedLinks, showLines, links]);

  const jdSpansBySentence = useMemo(() => {
    const map = new Map<number, { start: number; end: number; linkIdx: number; color: string }[]>();
    links.forEach((l, i) => {
      const arr = map.get(l.jd_sentence_index) ?? [];
      arr.push({ start: l.jd_start, end: l.jd_end, linkIdx: i, color: colorFor(l.canonical) });
      map.set(l.jd_sentence_index, arr);
    });
    return map;
  }, [links]);

  const resumeSpansBySentence = useMemo(() => {
    const map = new Map<number, { start: number; end: number; linkIdx: number; color: string }[]>();
    links.forEach((l, i) => {
      const arr = map.get(l.resume_sentence_index) ?? [];
      arr.push({
        start: l.resume_start,
        end: l.resume_end,
        linkIdx: i,
        color: colorFor(l.canonical),
      });
      map.set(l.resume_sentence_index, arr);
    });
    return map;
  }, [links]);

  const sentenceHasHover = (side: "jd" | "resume", index: number) => {
    if (hoverIdx === null) return false;
    const l = links[hoverIdx];
    return l
      ? side === "jd"
        ? l.jd_sentence_index === index
        : l.resume_sentence_index === index
      : false;
  };

  const toggleCls =
    "flex cursor-pointer items-center gap-2 rounded-sm border border-line bg-inset px-2.5 py-1.5 font-mono text-[11px] text-muted transition-colors hover:text-ink";

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-4 py-2.5 sm:px-5">
        <h3 className="font-mono text-[11px] font-semibold uppercase tracking-[0.18em] text-ink">
          Match map
        </h3>
        <div className="flex flex-wrap items-center gap-2">
          <label className={toggleCls}>
            <input
              type="checkbox"
              checked={showLines}
              onChange={(e) => setShowLines(e.target.checked)}
              className="accent-[var(--accent)]"
            />
            Show connecting lines
          </label>
          <label className={toggleCls}>
            <input
              type="checkbox"
              checked={requiredOnly}
              onChange={(e) => setRequiredOnly(e.target.checked)}
              className="accent-[var(--accent)]"
            />
            Required only
          </label>
          <span className="font-mono text-[11px] tabular-nums text-faint">
            {displayedLinks.length}/{links.length} drawn
          </span>
        </div>
      </div>

      <div ref={containerRef} className="relative p-4 sm:p-5">
        <div className="grid gap-8 lg:grid-cols-2">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-faint">
                Job description
              </span>
              <span className="font-mono text-[11px] tabular-nums text-faint">
                {jd_sentences.length} lines
              </span>
            </div>
            <div className="rounded-md border border-line bg-inset p-4">
              {jd_sentences.map((s) => (
                <div
                  key={`jd-${s.index}`}
                  className={`rounded-sm px-2 py-1.5 text-sm leading-relaxed transition-colors ${
                    sentenceHasHover("jd", s.index) ? "bg-line/40" : ""
                  }`}
                >
                  <HighlightedText
                    text={s.text}
                    sentenceStart={s.start}
                    spans={jdSpansBySentence.get(s.index) ?? []}
                    side="jd"
                    hoverIdx={hoverIdx}
                    onHover={setHoverIdx}
                  />
                </div>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-faint">
                Resume
              </span>
              <span className="font-mono text-[11px] tabular-nums text-faint">
                {resume_sentences.length} lines
              </span>
            </div>
            <div className="rounded-md border border-line bg-inset p-4">
              {resume_sentences.map((s) => (
                <div
                  key={`resume-${s.index}`}
                  className={`rounded-sm px-2 py-1.5 text-sm leading-relaxed transition-colors ${
                    sentenceHasHover("resume", s.index) ? "bg-line/40" : ""
                  }`}
                >
                  <HighlightedText
                    text={s.text}
                    sentenceStart={s.start}
                    spans={resumeSpansBySentence.get(s.index) ?? []}
                    side="resume"
                    hoverIdx={hoverIdx}
                    onHover={setHoverIdx}
                  />
                </div>
              ))}
            </div>
          </div>
        </div>

        {showLines && lines.length > 0 && (
          <svg
            className="pointer-events-none absolute inset-0 h-full w-full"
            style={{ overflow: "visible" }}
          >
            {lines.map((ln) => {
              const dx = Math.max(24, (ln.to.x - ln.from.x) / 2);
              const active = hoverIdx === null || hoverIdx === ln.linkIdx;
              return (
                <g key={ln.linkIdx}>
                  <path
                    d={`M ${ln.from.x} ${ln.from.y} C ${ln.from.x + dx} ${ln.from.y}, ${ln.to.x - dx} ${ln.to.y}, ${ln.to.x} ${ln.to.y}`}
                    fill="none"
                    stroke={ln.color}
                    strokeWidth={hoverIdx !== null && !active ? 1.5 : 2.5}
                    strokeOpacity={active ? 0.85 : 0.12}
                    pointerEvents="stroke"
                    onMouseEnter={() => setHoverIdx(ln.linkIdx)}
                    onMouseLeave={() => setHoverIdx(null)}
                    className="cursor-pointer"
                  />
                  <circle
                    cx={ln.to.x}
                    cy={ln.to.y}
                    r={active ? 3.5 : 2}
                    fill={ln.color}
                    opacity={active ? 0.95 : 0.15}
                    pointerEvents="none"
                  />
                  {(hoverIdx === null || hoverIdx === ln.linkIdx) && (
                    <g
                      transform={`translate(${(ln.from.x + ln.to.x) / 2}, ${(ln.from.y + ln.to.y) / 2})`}
                      pointerEvents="none"
                    >
                      <text
                        textAnchor="middle"
                        fontSize="11"
                        fontWeight="600"
                        fill={ln.color}
                        style={{ paintOrder: "stroke", stroke: PANEL, strokeWidth: 4 }}
                      >
                        {ln.canonical}
                      </text>
                    </g>
                  )}
                </g>
              );
            })}
          </svg>
        )}
      </div>

      {hoverIdx !== null && links[hoverIdx] && (
        <div className="mx-4 mb-4 flex flex-wrap items-center gap-x-4 gap-y-1 rounded-md border border-line bg-panel-2 px-3 py-2 font-mono text-xs sm:mx-5 sm:mb-5">
          <span className="font-semibold" style={{ color: colorFor(links[hoverIdx].canonical) }}>
            {links[hoverIdx].jd_term}
          </span>
          <span className="text-faint">
            {links[hoverIdx].required ? "required" : "nice-to-have"} ·{" "}
            {links[hoverIdx].category}
          </span>
          <span className="text-faint">→</span>
          <span className="text-ink">{links[hoverIdx].resume_term || "(contextual)"}</span>
          <span className="text-faint">
            {QUALITY_LABEL[links[hoverIdx].quality]} · score{" "}
            {Math.round(links[hoverIdx].score * 100)}%
          </span>
        </div>
      )}

      {links.length === 0 && (
        <p className="mx-4 mb-4 rounded-md border border-dashed border-line-strong px-4 py-6 text-center font-mono text-xs text-muted sm:mx-5 sm:mb-5">
          No overlapping terms found between the JD and resume.
        </p>
      )}
    </div>
  );
}
