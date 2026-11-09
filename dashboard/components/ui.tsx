import Link from "next/link";
import type { ReactNode } from "react";
import type { OrderStatus } from "@/lib/types";

/** A register panel: red margin line on the left, ruled above and below. No box, no shadow. */
export function Register({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`border-y border-rule border-l-2 border-l-red/55 ${className}`}>{children}</section>;
}

/** Older name, same panel. */
export const Card = Register;

export function PageTitle({ children, sub, aside }: { children: ReactNode; sub?: ReactNode; aside?: ReactNode }) {
  return (
    <div className="mb-7 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="font-serif text-[28px] leading-tight font-semibold tracking-tight sm:text-[34px]">{children}</h1>
        {sub && <p className="mt-1.5 max-w-prose text-[15px] text-soft">{sub}</p>}
      </div>
      {aside}
    </div>
  );
}

export function SectionTitle({ children, aside }: { children: ReactNode; aside?: ReactNode }) {
  return (
    <div className="mb-3 flex items-baseline justify-between gap-3">
      <h2 className="font-serif text-[19px] font-semibold tracking-tight">{children}</h2>
      {aside && <span className="text-sm text-soft">{aside}</span>}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="px-4 py-8 text-[15px] text-soft sm:px-6">{children}</p>;
}

const STATUS_STYLES: Record<string, string> = {
  open: "text-soft",
  delivered: "text-green",
  cancelled: "text-soft line-through",
  pending: "text-red",
  overdue: "text-red",
};

const STATUS_LABELS: Record<string, string> = {
  open: "Open",
  delivered: "Delivered",
  cancelled: "Cancelled",
  pending: "Needs your answer",
  overdue: "Overdue",
};

/** A written status note, not a pill. */
export function Badge({ status }: { status: OrderStatus | "pending" | "overdue" | string }) {
  return (
    <span className={`shrink-0 text-sm font-medium ${STATUS_STYLES[status] ?? STATUS_STYLES.open}`}>
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

/** Register summary boxes: double rule on top, single below, columns split by vertical rules. */
export function SummaryRow({ stats, size = "lg" }: { stats: Stat[]; size?: "lg" | "md" }) {
  const four = stats.length === 4;
  return (
    <div
      className={`grid grid-cols-2 border-t-[3px] border-b border-double border-t-ink/35 border-b-rule ${
        four ? "lg:grid-cols-4" : "sm:grid-cols-4"
      }`}
    >
      {stats.map((s, i) => {
        const body = (
          <>
            <span className="block text-sm text-soft">{s.label}</span>
            <span
              className={`num mt-1.5 block leading-none ${size === "lg" ? "text-[34px] sm:text-[40px]" : "text-[19px]"} ${
                s.alert ? "text-red" : "text-ink"
              }`}
            >
              {s.value}
            </span>
            {s.note && <span className="mt-2 block text-[13px] text-soft">{s.note}</span>}
          </>
        );
        // Two columns on phones, one row when wide. Literal class names so Tailwind sees them.
        const cls = [
          "block py-4",
          i % 2 ? "border-l border-rule pl-4 sm:pl-5" : "pr-4",
          i >= 2 ? (four ? "border-t border-rule lg:border-t-0" : "border-t border-rule sm:border-t-0") : "",
          i === 2 ? (four ? "lg:border-l lg:pl-5" : "sm:border-l sm:pl-5") : "",
        ].join(" ");
        return s.href ? (
          <Link key={s.label} href={s.href} className={`${cls} transition-colors duration-150 hover:bg-paper-2/70`}>
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
