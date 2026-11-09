import type { Metadata } from "next";
import Link from "next/link";
import { Badge, Card, Empty, PageTitle } from "@/components/ui";
import { fieldLabel, fmtChangeValue, fmtTime } from "@/lib/format";
import { db, must } from "@/lib/supabase";
import type { PendingConfirmation } from "@/lib/types";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Pending" };

export default async function PendingPage() {
  const items = must<PendingConfirmation[]>(
    await db()
      .from("pending_confirmations")
      .select("*, clients(name)")
      .eq("status", "pending")
      .order("created_at", { ascending: false })
      .limit(100),
  );

  return (
    <>
      <PageTitle sub="Items Recall wasn't sure about. The owner confirms them on WhatsApp; nothing is saved until then.">
        Pending confirmations
      </PageTitle>
      {items.length === 0 ? (
        <Card>
          <Empty>All clear. Nothing waiting for confirmation.</Empty>
        </Card>
      ) : (
        <ul className="space-y-3">
          {items.map((p) => (
            <li key={p.id}>
              <Card className="p-4">
                <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                  <span className="text-sm text-muted">{p.clients?.name ?? "Unknown client"}</span>
                  <span className="text-xs text-muted">
                    {fmtTime(p.created_at)}
                    {p.call_id != null && (
                      <>
                        {" · "}
                        <Link href={`/calls#call-${p.call_id}`} className="underline hover:text-ink">
                          call #{p.call_id}
                        </Link>
                      </>
                    )}
                  </span>
                </div>
                <p className="mt-2 flex items-start gap-2 font-medium">
                  <Badge status="pending" />
                  <span>{p.question}</span>
                </p>
                <Extracted data={p.extracted_json} />
                <Options options={p.options} />
              </Card>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

function scalar(v: unknown): string {
  if (v === null || v === undefined || v === "") return "—";
  return typeof v === "object" ? JSON.stringify(v) : String(v);
}

function Extracted({ data }: { data: Record<string, unknown> | null }) {
  if (!data || typeof data !== "object") return null;
  const entries = Object.entries(data).filter(([, v]) => v !== null && v !== undefined && v !== "");
  if (!entries.length) return null;
  return (
    <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 rounded-lg bg-line/40 p-3 text-sm">
      {entries.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-muted">{fieldLabel(k)}</dt>
          <dd className="break-words font-medium">{fmtChangeValue(k, scalar(v))}</dd>
        </div>
      ))}
    </dl>
  );
}

/** options holds candidate order ids for the owner's buttons. */
function Options({ options }: { options: unknown }) {
  const ids = Array.isArray(options)
    ? options
        .map((o) => (typeof o === "object" && o !== null ? (o as Record<string, unknown>).order_id ?? (o as Record<string, unknown>).id : o))
        .filter((o): o is number | string => typeof o === "number" || (typeof o === "string" && /^\d+$/.test(o)))
    : [];
  if (!ids.length) return null;
  return (
    <p className="mt-3 flex flex-wrap items-center gap-2 text-sm">
      <span className="text-muted">Candidates:</span>
      {ids.map((id) => (
        <Link key={id} href={`/orders/${id}`} className="rounded-md border border-line px-2 py-0.5 hover:border-accent hover:text-accent">
          #{id}
        </Link>
      ))}
    </p>
  );
}
