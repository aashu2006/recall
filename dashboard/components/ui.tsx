import type { ReactNode } from "react";
import type { OrderStatus } from "@/lib/types";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`rounded-xl border border-line bg-surface ${className}`}>{children}</section>;
}

export function PageTitle({ children, sub }: { children: ReactNode; sub?: ReactNode }) {
  return (
    <div className="mb-5">
      <h1 className="text-xl font-semibold tracking-tight">{children}</h1>
      {sub && <p className="mt-1 text-sm text-muted">{sub}</p>}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="px-4 py-8 text-center text-sm text-muted">{children}</p>;
}

const STATUS_STYLES: Record<string, string> = {
  open: "bg-sky-500/10 text-sky-700 dark:text-sky-300",
  delivered: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  cancelled: "bg-zinc-500/10 text-zinc-600 dark:text-zinc-400 line-through",
  pending: "bg-amber-500/15 text-amber-700 dark:text-amber-300",
  overdue: "bg-red-500/10 text-red-700 dark:text-red-300",
};

export function Badge({ status }: { status: OrderStatus | "pending" | "overdue" | string }) {
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium capitalize ${
        STATUS_STYLES[status] ?? STATUS_STYLES.open
      }`}
    >
      {status}
    </span>
  );
}
