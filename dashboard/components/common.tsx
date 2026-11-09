import Link from "next/link";
import type { ReactNode } from "react";
import { Card } from "@/components/ui/card";

export function PageHeader({ title, description, aside }: { title: ReactNode; description?: ReactNode; aside?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-x-6 gap-y-2">
      <div className="min-w-0">
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="mt-1 text-muted-foreground">{description}</p>}
      </div>
      {aside && <div className="text-muted-foreground">{aside}</div>}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="px-4 py-10 text-center text-muted-foreground">{children}</p>;
}

export function StatCard({ label, value, href, alert }: { label: string; value: ReactNode; href?: string; alert?: boolean }) {
  const body = (
    <Card size="sm" className="gap-1 px-4 transition-colors">
      <p className="text-[13px] text-muted-foreground">{label}</p>
      <p className={`num text-2xl font-medium ${alert ? "text-destructive" : ""}`}>{value}</p>
    </Card>
  );
  return href ? (
    <Link href={href} className="block rounded-xl [&>div]:hover:bg-muted/50">
      {body}
    </Link>
  ) : (
    body
  );
}

/** Units sit softer than the figure they belong to. */
export function Unit({ children }: { children: ReactNode }) {
  return children ? <span className="ml-1 font-sans text-muted-foreground">{children}</span> : null;
}
