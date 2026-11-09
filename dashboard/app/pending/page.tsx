import type { Metadata } from "next";
import Link from "next/link";
import PendingOptions from "@/app/pending/PendingOptions";
import { Empty, PageHeader } from "@/components/common";
import { Card } from "@/components/ui/card";
import { fmtDate, fmtNum, fmtRate, fmtTime } from "@/lib/format";
import { Highlight } from "@/lib/highlight";
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
      <PageHeader
        title="Pending"
        description="When Recall isn't sure, it asks instead of guessing. Nothing is saved until you answer, here or on WhatsApp."
        aside={items.length > 0 && `${items.length} waiting`}
      />
      <Card className="gap-0 py-0">
        {items.length === 0 ? (
          <Empty>Nothing is waiting for an answer.</Empty>
        ) : (
          <ul className="divide-y">
            {items.map((p) => (
              <li key={p.id}>
                <PendingEntry p={p} />
              </li>
            ))}
          </ul>
        )}
      </Card>
    </>
  );
}

interface ExtractedItem {
  kind?: string;
  item?: string | null;
  order_ref?: string | null;
  spec?: string | null;
  quantity?: number | string | null;
  unit?: string | null;
  rate?: number | string | null;
  delivery_date?: string | null;
  evidence?: string | null;
}

/** extracted_json is {item, clip, decision} from the pipeline; older rows may be the bare item. */
function extractedItem(data: Record<string, unknown> | null): ExtractedItem {
  if (!data || typeof data !== "object") return {};
  const inner = data.item;
  return (inner && typeof inner === "object" ? inner : data) as ExtractedItem;
}

function PendingEntry({ p }: { p: PendingConfirmation }) {
  const it = extractedItem(p.extracted_json);
  // The WhatsApp message puts the quote on its own line after the question; show it separately.
  const question = p.question.split("\n")[0];
  const facts = [
    [it.item ?? it.order_ref, it.spec].filter(Boolean).join(" "),
    it.quantity != null ? `${fmtNum(it.quantity)} ${it.unit ?? ""}`.trim() : "",
    it.rate != null ? fmtRate(it.rate, it.unit) : "",
    it.delivery_date ? `due ${fmtDate(it.delivery_date)}` : "",
  ].filter(Boolean);

  return (
    <div className="px-4 py-4">
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
        <p className="font-medium">{question}</p>
        <p className="text-[13px] text-muted-foreground">
          {p.clients?.name ?? "Unknown client"}
          <span className="mx-1.5">·</span>
          <span className="tabular-nums">{fmtTime(p.created_at)}</span>
          {p.call_id != null && (
            <>
              <span className="mx-1.5">·</span>
              <Link href={`/calls#call-${p.call_id}`} className="hover:text-foreground">
                Call <span className="num">#{p.call_id}</span>
              </Link>
            </>
          )}
        </p>
      </div>
      {it.evidence && (
        <p lang="hi" className="mt-1 max-w-prose text-muted-foreground">
          &ldquo;
          <Highlight text={it.evidence} />
          &rdquo;
        </p>
      )}
      {facts.length > 0 && <p className="mt-1 text-[13px] text-muted-foreground">Heard: {facts.join(" · ")}</p>}
      <PendingOptions id={p.id} options={optionValues(p.options)} />
    </div>
  );
}

/** Option values from the pipeline: order ids and "new" ("no" is always offered). Older rows may hold objects. */
function optionValues(options: unknown): string[] {
  return (Array.isArray(options) ? options : [])
    .map((o) => (typeof o === "object" && o !== null ? ((o as Record<string, unknown>).order_id ?? (o as Record<string, unknown>).id) : o))
    .filter((o): o is number | string => typeof o === "number" || typeof o === "string")
    .map(String)
    .filter((o) => o === "new" || /^\d+$/.test(o))
    .slice(0, 2);
}
