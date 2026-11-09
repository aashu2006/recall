import Link from "next/link";
import type { ReactNode } from "react";
import type { OrderStatus } from "@/lib/types";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`rounded-xl border border-line bg-surface ${className}`}>{children}</section>;
}

export function PageTitle({ children, sub, aside }: { children: ReactNode; sub?: ReactNode; aside?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-[22px] font-semibold tracking-tight sm:text-[26px]">{children}</h1>
        {sub && <p className="mt-1 max-w-prose text-sm text-muted">{sub}</p>}
      </div>
      {aside}
    </div>
  );
}

export function SectionTitle({ children, aside }: { children: ReactNode; aside?: ReactNode }) {
  return (
    <div className="mb-3 flex items-baseline justify-between gap-3">
      <h2 className="text-[17px] font-semibold tracking-tight">{children}</h2>
      {aside && <span className="text-sm text-muted">{aside}</span>}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="px-4 py-10 text-center text-sm text-muted">{children}</p>;
}

const STATUS_STYLES: Record<string, string> = {
  open: "border-line text-muted",
  delivered: "border-now/40 text-now",
  cancelled: "border-line text-muted line-through",
  pending: "border-accent/50 text-accent",
  overdue: "border-was/50 text-was",
};

const STATUS_LABELS: Record<string, string> = {
  open: "Open",
  delivered: "Delivered",
  cancelled: "Cancelled",
  pending: "Needs you",
  overdue: "Overdue",
};

export function Badge({ status }: { status: OrderStatus | "pending" | "overdue" | string }) {
  return (
    <span
      className={`inline-flex shrink-0 items-center rounded-full border px-2 py-0.5 text-xs font-medium ${
        STATUS_STYLES[status] ?? STATUS_STYLES.open
      }`}
    >
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}

export interface Stat {
  label: string;
  value: number;
  note?: string;
  href?: string;
  /** Draw attention: the number is in the accent colour. */
  alert?: boolean;
}

/** One ruled band of headline numbers, like the header row of a ledger page. */
export function StatStrip({ stats }: { stats: Stat[] }) {
  return (
    <Card className="grid grid-cols-2 overflow-hidden lg:grid-cols-4">
      {stats.map((s, i) => {
        const body = (
          <>
            <span className="text-sm text-muted">{s.label}</span>
            <span
              key={s.value}
              className={`fresh mt-1 block text-[34px] leading-none font-semibold tracking-tight sm:text-[40px] ${
                s.alert ? "text-accent" : ""
              }`}
            >
              {s.value}
            </span>
            {s.note && <span className="mt-2 block text-xs text-muted">{s.note}</span>}
          </>
        );
        const cls = `block p-4 sm:p-5 ${i % 2 ? "border-l border-line" : ""} ${i >= 2 ? "border-t border-line lg:border-t-0" : ""} ${
          i === 2 ? "lg:border-l" : ""
        }`;
        return s.href ? (
          <Link key={s.label} href={s.href} className={`${cls} transition-colors duration-150 hover:bg-raised/60`}>
            {body}
          </Link>
        ) : (
          <div key={s.label} className={cls}>
            {body}
          </div>
        );
      })}
    </Card>
  );
}
