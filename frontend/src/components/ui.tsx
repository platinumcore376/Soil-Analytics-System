'use client';

/* Small shared primitives. Kept in one file because each is a handful of lines and they
 * are always imported together. */

import Link from 'next/link';
import type { ReactNode } from 'react';

/* Icon glyphs (⚠ ℹ ‹ › and the bare "i") render as different shapes across Android OEM
 * emoji/symbol fonts — some render monochrome, some colored, some fall back to a tofu box
 * on older devices. Inline SVG with currentColor guarantees one look everywhere and follows
 * text color automatically. */

function ChevronLeftIcon() {
  return (
    <svg aria-hidden width="14" height="14" viewBox="0 0 24 24" fill="none">
      <path
        d="M15 5l-7 7 7 7"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function ChevronRightIcon() {
  return (
    <svg aria-hidden width="16" height="16" viewBox="0 0 24 24" fill="none">
      <path
        d="M9 5l7 7-7 7"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function WarningIcon() {
  return (
    <svg aria-hidden width="16" height="16" viewBox="0 0 24 24" fill="none">
      <path
        d="M12 4 2 20h20L12 4Z"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinejoin="round"
      />
      <path d="M12 10v4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      <circle cx="12" cy="17" r="1" fill="currentColor" />
    </svg>
  );
}

function InfoIcon() {
  return (
    <svg aria-hidden width="16" height="16" viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2" />
      <path d="M12 11v5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      <circle cx="12" cy="8" r="1" fill="currentColor" />
    </svg>
  );
}

export function Card({
  children,
  className = '',
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`rounded-2xl border border-black/10 bg-white p-4 shadow-sm ${className}`}
    >
      {children}
    </section>
  );
}

export function SectionTitle({ children }: { children: ReactNode }) {
  return <h2 className="mb-3 text-lg font-semibold">{children}</h2>;
}

/* The one <h1> on a screen.
 *
 * SectionTitle is fixed at <h2>, so before this every route's outline started at h2 and
 * /signin had a hand-rolled <h1 className="text-2xl font-bold">. Screen-reader users
 * navigating by heading level got no document title on any page.
 */
export function PageTitle({ children }: { children: ReactNode }) {
  return <h1 className="mb-3 text-2xl font-bold">{children}</h1>;
}

/** Primary action. Large, full-width — designed for one-handed outdoor use. */
export function BigButton({
  children,
  onClick,
  href,
  disabled,
  variant = 'primary',
  icon,
  hint,
}: {
  children: ReactNode;
  onClick?: () => void;
  href?: string;
  disabled?: boolean;
  variant?: 'primary' | 'secondary';
  icon?: string;
  hint?: string;
}) {
  const base =
    'flex w-full items-center gap-3 rounded-2xl px-4 py-4 text-left text-lg font-semibold transition disabled:opacity-50';
  const style =
    variant === 'primary'
      ? 'bg-ok text-white active:bg-ok/90'
      : 'border-2 border-ok/30 bg-white text-ink active:bg-surface';

  const inner = (
    <>
      {icon && (
        <span aria-hidden className="text-3xl">
          {icon}
        </span>
      )}
      <span className="flex-1">
        {children}
        {hint && (
          <span className="block text-sm font-normal opacity-80">{hint}</span>
        )}
      </span>
      <span aria-hidden className="opacity-60">
        <ChevronRightIcon />
      </span>
    </>
  );

  if (href && !disabled) {
    return (
      <Link href={href} className={`${base} ${style}`}>
        {inner}
      </Link>
    );
  }
  return (
    <button onClick={onClick} disabled={disabled} className={`${base} ${style}`}>
      {inner}
    </button>
  );
}

export function Spinner({ label }: { label: string }) {
  return (
    <div role="status" className="flex flex-col items-center gap-3 py-10">
      <span
        aria-hidden
        className="h-10 w-10 animate-spin rounded-full border-4 border-ok/25 border-t-ok"
      />
      <p className="text-muted">{label}</p>
    </div>
  );
}

/* role="alert" so a screen reader announces the failure. Without it an error that appears
 * after an async call is silent to anyone not watching the screen. */
export function ErrorNote({
  message,
  onRetry,
  retryLabel,
}: {
  message: string;
  onRetry?: () => void;
  retryLabel?: string;
}) {
  return (
    <Card className="border-low/30">
      <p role="alert" className="flex items-start gap-2 text-low-text">
        <span aria-hidden className="mt-0.5">
          <WarningIcon />
        </span>
        <span>{message}</span>
      </p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-3 w-full rounded-xl border-2 border-low/30 py-2 font-semibold text-low-text"
        >
          {/* Callers that pass onRetry are expected to pass a translated label too; the
            * English fallback exists only so the button is never blank. */}
          {retryLabel ?? 'Retry'}
        </button>
      )}
    </Card>
  );
}

/* Collapsible help text — the spec's "contextual help tooltips". A <details> rather than a
 * hover tooltip on purpose: hover does not exist on a phone, and this stays open while the
 * farmer reads it and types. Native disclosure also means keyboard and screen-reader
 * support come for free.
 */
export function HelpNote({ summary, children }: { summary: string; children: ReactNode }) {
  return (
    <details className="mt-1 text-sm">
      <summary className="inline-flex cursor-pointer list-none items-center gap-1.5 text-ok-text">
        <span
          aria-hidden
          className="inline-flex h-5 w-5 items-center justify-center rounded-full border border-ok"
        >
          <InfoIcon />
        </span>
        <span className="underline">{summary}</span>
      </summary>
      <p className="mt-2 rounded-xl bg-surface p-3 text-ink/80">{children}</p>
    </details>
  );
}

/* Inline field-level message. `tone` decides whether this blocks submission (error) or is
 * only advisory (warn) — a pH of 9.5 is real but worth a second look, whereas 99 is a typo.
 */
export function FieldNote({ tone, message }: { tone: 'error' | 'warn'; message: string }) {
  const style = tone === 'error' ? 'text-low-text' : 'text-caution-text';
  return (
    <p className={`mt-1 flex items-start gap-1.5 text-sm ${style}`}>
      <span aria-hidden className="mt-0.5">
        {tone === 'error' ? <WarningIcon /> : <InfoIcon />}
      </span>
      <span>{message}</span>
    </p>
  );
}

/* Skeleton placeholder. Shown instead of a whole-screen spinner when the page's layout is
 * already known, so the screen does not collapse and re-expand while data arrives. */
export function Skeleton({ className = '' }: { className?: string }) {
  return (
    <span
      aria-hidden
      className={`block animate-pulse rounded-xl bg-black/10 ${className}`}
    />
  );
}

/** Status chip: colour + icon + word, so meaning survives greyscale. */
export function StatusChip({
  bg,
  icon,
  label,
}: {
  bg: string;
  icon: string;
  label: string;
}) {
  return (
    <span
      className={`inline-flex shrink-0 items-center gap-1 rounded-full px-3 py-1 text-sm font-bold text-white ${bg}`}
    >
      <span aria-hidden>{icon}</span>
      {label}
    </span>
  );
}

/* Inset panel — a subdued block INSIDE a Card.
 *
 * The three classes `rounded-xl bg-surface p-3` were repeated verbatim in three files
 * (HelpNote body, the fertilizer product rows, AddFieldForm). Naming it stops the next copy
 * drifting, and makes the visual hierarchy explicit: Card is the panel, Subpanel is a block
 * nested one level in, so it deliberately uses a smaller radius and padding than Card.
 */
export function Subpanel({
  children,
  className = '',
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={`rounded-xl bg-surface p-3 ${className}`}>{children}</div>;
}

/* Back link.
 *
 * The capture flow is three screens deep (field -> method -> camera -> readings) and had no
 * in-app way back: the farmer's only option was the browser's system back button, which is
 * hidden in a standalone PWA. `display: standalone` in the manifest removes the browser
 * chrome entirely, so without this there is genuinely no way to correct a wrong turn.
 *
 * An explicit `href` rather than `router.back()`: history is unreliable here because several
 * screens `router.replace` on guard failures, so "back" could land somewhere unexpected.
 */
export function BackLink({ href, label }: { href: string; label: string }) {
  return (
    <Link
      href={href}
      data-compact
      className="-ml-1 inline-flex items-center gap-1 self-start px-1 text-sm font-medium text-muted"
    >
      <span aria-hidden>
        <ChevronLeftIcon />
      </span>
      {label}
    </Link>
  );
}