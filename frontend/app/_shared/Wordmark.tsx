import Link from "next/link";

/** The FairHire mark: an F whose stem ends in a check. Same drawing as app/icon.svg. */
export function LogoMark({ size = 28 }: { size?: number }) {
  return (
    <svg viewBox="0 0 32 32" width={size} height={size} aria-hidden="true" className="shrink-0">
      <rect width="32" height="32" rx="7" fill="var(--accent)" />
      <path
        d="M7 19l5 5V8h12M12 16h8" fill="none" stroke="#fff"
        strokeWidth="4" strokeLinecap="round" strokeLinejoin="round"
      />
    </svg>
  );
}

/**
 * Mark plus name. Links home when given `href`; otherwise renders as plain text.
 * `labelClassName` lets a caller hide the name (the editor bar drops it on narrow screens).
 */
export function Wordmark({ href, className = "", labelClassName }: {
  href?: string; className?: string; labelClassName?: string;
}) {
  const content = (<><LogoMark /><span className={labelClassName}>FairHire</span></>);
  const cls = `inline-flex items-center gap-2.5 font-semibold tracking-[-0.01em] no-underline ${className}`;
  return href ? <Link href={href} className={cls}>{content}</Link> : <span className={cls}>{content}</span>;
}
