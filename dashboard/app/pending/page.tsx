import type { Metadata } from "next";
import Link from "next/link";
import { Card, Empty, PageTitle } from "@/components/ui";
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
      <PageTitle sub="When Recall isn't sure, it asks you on WhatsApp instead of guessing. Nothing is saved until you tap an answer.">
        Waiting for your answer
      </PageTitle>
      {items.length === 0 ? (
        <Card>
          <Empty>All clear. Nothing is waiting for you.</Empty>
        </Card>
      ) : (
        <ul className="grid gap-4 lg:grid-cols-2">
          {items.map((p) => (
            <li key={p.id} className="fresh">
              <PendingCard p={p} />
            </li>
          ))}
        </ul>
      )}
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

function PendingCard({ p }: { p: PendingConfirmation }) {
  const it = extractedItem(p.extracted_json);
  // The WhatsApp message puts the quote on its own line after the question; show it separately.
  const question = p.question.split("\n")[0];
  const facts: [string, string][] = [];
  if (it.item || it.order_ref) facts.push(["Item", [it.item ?? it.order_ref, it.spec].filter(Boolean).join(" ")]);
  if (it.quantity != null) facts.push(["Quantity", `${fmtNum(it.quantity)} ${it.unit ?? ""}`.trim()]);
  if (it.rate != null) facts.push(["Rate", fmtRate(it.rate, it.unit)]);
  if (it.delivery_date) facts.push(["Delivery", fmtDate(it.delivery_date)]);

  return (
    <Card className="flex h-full flex-col border-accent/35">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 px-4 pt-4 sm:px-5">
        <p className="font-medium">{p.clients?.name ?? "Unknown client"}</p>
        <p className="text-sm text-muted">
          {fmtTime(p.created_at)}
          {p.call_id != null && (
            <>
              {", "}
              <Link href={`/calls#call-${p.call_id}`} className="rounded underline decoration-line underline-offset-4 hover:text-ink">
                call #{p.call_id}
              </Link>
            </>
          )}
        </p>
      </div>

      <div className="flex-1 px-4 pt-3 pb-4 sm:px-5">
        <h2 className="text-[17px] leading-snug font-semibold">{question}</h2>
        {it.evidence && (
          <blockquote lang="hi" className="mt-3 border-l-2 border-accent/60 pl-4 text-[17px] text-ink/90">
            &ldquo;<Highlight text={it.evidence} />&rdquo;
          </blockquote>
        )}
        {facts.length > 0 && (
          <dl className="mt-4 flex flex-wrap gap-2">
            {facts.map(([k, v]) => (
              <div key={k} className="rounded-lg border border-line px-3 py-1.5">
                <dt className="text-xs text-muted">{k}</dt>
                <dd className="font-medium">{v}</dd>
              </div>
            ))}
          </dl>
        )}
      </div>

      <div className="border-t border-line bg-raised/50 px-4 py-3.5 sm:px-5">
        <p className="mb-2.5 text-sm text-muted">Your options on WhatsApp</p>
        <Options options={p.options} />
      </div>
    </Card>
  );
}

/** The owner's WhatsApp buttons: candidate order ids, "new", and always a "no". */
function Options({ options }: { options: unknown }) {
  const opts = (Array.isArray(options) ? options : [])
    .map((o) => (typeof o === "object" && o !== null ? ((o as Record<string, unknown>).order_id ?? (o as Record<string, unknown>).id) : o))
    .filter((o): o is number | string => typeof o === "number" || typeof o === "string")
    .slice(0, 2);
  const btn = "inline-flex items-center gap-1.5 rounded-full border px-3.5 py-1.5 text-sm font-medium";
  return (
    <div className="flex flex-wrap gap-2">
      {opts.map((o) =>
        String(o) === "new" ? (
          <span key="new" className={`${btn} border-line`}>
            Naya order
          </span>
        ) : /^\d+$/.test(String(o)) ? (
          <Link
            key={o}
            href={`/orders/${o}`}
            className={`${btn} border-line transition-colors duration-150 hover:border-accent hover:text-accent`}
            title={`Open order #${o}`}
          >
            Order #{o}
          </Link>
        ) : null,
      )}
      <span className={`${btn} border-line text-muted`}>Nahi</span>
    </div>
  );
}
