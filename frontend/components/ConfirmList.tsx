"use client";

import type { ConfirmItem } from "../lib/api";

function KindChip({ kind, required }: { kind: string; required: boolean }) {
  return (
    <span className="rounded-sm bg-inset px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-[0.1em] text-muted">
      {kind}
      {required ? "" : " · nice-to-have"}
    </span>
  );
}

export default function ConfirmList({
  items,
  answers,
  onAnswer,
  onApply,
  applied,
  busy,
}: {
  items: ConfirmItem[];
  answers: Record<string, boolean>;
  onAnswer: (term: string, value: boolean) => void;
  onApply: () => void;
  applied: boolean;
  busy: boolean;
}) {
  if (items.length === 0) return null;

  const answeredCount = items.reduce(
    (n, it) => n + (answers[it.term.toLowerCase()] !== undefined ? 1 : 0),
    0
  );
  const canApply = answeredCount > 0 && !busy;

  return (
    <div className="overflow-hidden rounded-md border border-line bg-panel">
      <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-2.5">
        <div>
          <h3 className="font-mono text-[11px] font-semibold uppercase tracking-[0.18em] text-ink">
            Confirm your skills
          </h3>
          <p className="mt-0.5 text-xs text-muted">
            These weren&rsquo;t clearly found in the resume — answer them all, then apply once.
            The score won&rsquo;t assume anything until you say so.
          </p>
        </div>
        <span className="shrink-0 font-mono text-[11px] tabular-nums text-faint">
          {answeredCount}/{items.length} answered
        </span>
      </div>

      <ul className="divide-y divide-line">
        {items.map((it) => {
          const key = it.term.toLowerCase();
          const answer = answers[key];
          const btnCls = (active: boolean) =>
            `rounded-md border px-3 py-1.5 font-mono text-[11px] transition ${
              active
                ? "border-accent bg-accent text-accent-ink"
                : "border-line bg-inset text-muted hover:text-ink"
            }`;
          return (
            <li key={key} className="px-4 py-3">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <KindChip kind={it.kind} required={it.required} />
                    <span className="text-sm font-medium text-ink">{it.term}</span>
                  </div>
                  {it.suggested === null || !it.hint ? (
                    <p className="mt-1 text-xs leading-snug text-faint">
                      Not detected in the resume.
                    </p>
                  ) : (
                    <p className="mt-1 text-xs leading-snug text-faint">
                      LLM suggests: {it.suggested ? "likely yes" : "likely no"} — {it.hint}
                    </p>
                  )}
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => onAnswer(it.term, true)}
                    className={btnCls(answer === true)}
                  >
                    I have it
                  </button>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => onAnswer(it.term, false)}
                    className={btnCls(answer === false)}
                  >
                    No
                  </button>
                </div>
              </div>
            </li>
          );
        })}
      </ul>

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-4 py-3">
        <p className="font-mono text-[11px] text-faint">
          {applied
            ? "Answers applied to the score."
            : "Answer the items above, then re-score once."}
        </p>
        <button
          type="button"
          disabled={!canApply}
          onClick={onApply}
          className="rounded-md bg-accent px-4 py-2 font-mono text-[11px] font-semibold uppercase tracking-[0.14em] text-accent-ink transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {applied ? "Re-score with answers" : "Apply answers & re-score"}
        </button>
      </div>
    </div>
  );
}
