import Link from "next/link";
import type { ReactNode } from "react";
import type { OrderStatus } from "@/lib/types";

/** A register sheet: red margin line on the left, ruled above and below. No box, no shadow. */
export function Register({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`border-y border-rule border-l-2 border-l-red/50 bg-paper-3/60 ${className}`}>{children}</section>;
}

/** Older name, same sheet. */
export const Card = Register;

export function PageTitle({ children, sub, aside }: { children: ReactNode; sub?: ReactNode; aside?: ReactNode }) {
  return (
    <div className="mb-8 flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
      <div className="min-w-0">
        <h1 className="font-serif text-[30px] leading-[1.1] font-semibold tracking-tight sm:text-[40px]">{children}</h1>
        {sub && <p className="mt-2.5 max-w-[62ch] text-[15px] leading-relaxed text-soft">{sub}</p>}
      </div>
      {aside}
    </div>
  );
}

export function SectionTitle({ children, aside }: { children: ReactNode; aside?: ReactNode }) {
  return (
    <div className="mb-3 flex items-baseline justify-between gap-3">
      <h2 className="font-serif text-[20px] font-semibold tracking-tight">{children}</h2>
      {aside && <span className="text-sm text-soft">{aside}</span>}
    </div>
  );
}

export function Empty({ children, icon }: { children: ReactNode; icon?: "check" | "none" }) {
  return (
    <div className="flex items-center gap-3 px-5 py-9 text-[15px] text-soft sm:px-6">
      {icon === "check" && (
        <svg viewBox="0 0 20 20" className="h-5 w-5 shrink-0 text-green" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
          <circle cx="10" cy="10" r="8" />
          <path d="m6.5 10.2 2.3 2.3 4.7-4.9" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      )}
      <p>{children}</p>
    </div>
  );
}

const STATUS_STYLES: Record<string, string> = {
  open: "text-soft border-ink/20",
  delivered: "text-green border-green/35",
  cancelled: "text-soft border-ink/15 line-through",
  pending: "text-red border-red/35",
  overdue: "text-red border-red/35",
};

const STATUS_DOT: Record<string, string> = {
  open: "bg-ink/45",
  delivered: "bg-green",
  cancelled: "bg-ink/30",
  pending: "bg-red",
  overdue: "bg-red",
};

const STATUS_LABELS: Record<string, string> = {
  open: "Open",
  delivered: "Delivered",
  cancelled: "Cancelled",
  pending: "Needs your answer",
  overdue: "Overdue",
};

/** A small status tag with a dot, like a note in the register's margin. */
export function Badge({ status }: { status: OrderStatus | "pending" | "overdue" | string }) {
  return (
    <span
      className={`inline-flex shrink-0 items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[13px] font-medium whitespace-nowrap ${
        STATUS_STYLES[status] ?? STATUS_STYLES.open
      }`}
    >
      <span aria-hidden className={`h-1.5 w-1.5 rounded-full ${STATUS_DOT[status] ?? STATUS_DOT.open}`} />
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}

export interface Stat {
  label: string;
  value: ReactNode;
  note?: string;
  href?: string;
  /** Red ink: something needs the owner. */
  alert?: boolean;
}

/** Register totals: double rule on top, single below, columns split by vertical rules. */
export function SummaryRow({ stats, size = "lg" }: { stats: Stat[]; size?: "lg" | "md" }) {
  const four = stats.length === 4;
  return (
    <div
      className={`grid grid-cols-2 border-t-[3px] border-b border-double border-t-ink/40 border-b-rule ${
        four ? "lg:grid-cols-4" : "sm:grid-cols-4"
      }`}
    >
      {stats.map((s, i) => {
        const body = (
          <>
            <span className="label flex items-center justify-between gap-2">
              {s.label}
              {s.href && (
                <svg viewBox="0 0 16 16" className="h-3.5 w-3.5 text-faint transition-transform duration-150 group-hover:translate-x-0.5" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
                  <path d="M6 3.5 10.5 8 6 12.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              )}
            </span>
            <span
              className={`num block leading-none tracking-tight ${
                size === "lg" ? "mt-3 text-[40px] sm:text-[48px]" : "mt-2 text-[20px] font-medium sm:text-[22px]"
              } ${s.alert ? "text-red" : "text-ink"}`}
            >
              {s.value}
            </span>
            {s.note && <span className={`mt-2.5 block text-[13px] ${s.alert ? "text-red/85" : "text-soft"}`}>{s.note}</span>}
          </>
        );
        // Two columns on phones, one row when wide. Literal class names so Tailwind sees them.
        const cls = [
          size === "lg" ? "block py-5" : "block py-4",
          i % 2 ? "border-l border-rule pl-4 sm:pl-6" : "pr-4 sm:pr-6",
          i >= 2 ? (four ? "border-t border-rule lg:border-t-0" : "border-t border-rule sm:border-t-0") : "",
          i === 2 ? (four ? "lg:border-l lg:pl-6" : "sm:border-l sm:pl-6") : "",
          i === 1 ? (four ? "lg:pr-6" : "sm:pr-6") : "",
        ].join(" ");
        return s.href ? (
          <Link key={s.label} href={s.href} className={`group ${cls} transition-colors duration-150 hover:bg-paper-2/60`}>
            {body}
          </Link>
        ) : (
          <div key={s.label} className={cls}>
            {body}
          </div>
        );
      })}
    </div>
  );
}

/** "₹" and units sit smaller and softer than the figure they belong to. */
export function Unit({ children }: { children: ReactNode }) {
  return <span className="ml-1 text-[0.62em] font-normal tracking-normal text-soft">{children}</span>;
}
