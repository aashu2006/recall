import type { Metadata } from "next";
import Link from "next/link";
import { Badge, Empty, PageTitle, Register } from "@/components/ui";
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
      <Register>
        {items.length === 0 ? (
          <Empty>All clear. Nothing is waiting for you.</Empty>
        ) : (
          <ul className="divide-y divide-rule">
            {items.map((p) => (
              <li key={p.id} className="fresh">
                <PendingEntry p={p} />
              </li>
            ))}
          </ul>
        )}
      </Register>
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
  const facts: [string, string, boolean][] = [];
  if (it.item || it.order_ref) facts.push(["Item", [it.item ?? it.order_ref, it.spec].filter(Boolean).join(" "), false]);
  if (it.quantity != null) facts.push(["Quantity", `${fmtNum(it.quantity)} ${it.unit ?? ""}`.trim(), true]);
  if (it.rate != null) facts.push(["Rate", fmtRate(it.rate, it.unit), true]);
  if (it.delivery_date) facts.push(["Delivery", fmtDate(it.delivery_date), true]);

  return (
    <div className="grid gap-x-8 gap-y-3 px-4 py-5 sm:px-5 md:grid-cols-[230px_1fr]">
      <div className="min-w-0">
        <p className="text-[16px] font-medium">{p.clients?.name ?? "Unknown client"}</p>
        <p className="text-sm text-soft">
          <span className="num">{fmtTime(p.created_at)}</span>
          {p.call_id != null && (
            <>
              {", "}
              <Link href={`/calls#call-${p.call_id}`} className="rounded underline decoration-rule underline-offset-4 hover:text-ink">
                call <span className="num">#{p.call_id}</span>
              </Link>
            </>
          )}
        </p>
        <p className="mt-2">
          <Badge status="pending" />
        </p>
      </div>

      <div className="min-w-0">
        <h2 className="max-w-[60ch] font-serif text-[19px] leading-snug font-semibold">{question}</h2>
        {it.evidence && (
          <blockquote lang="hi" className="mt-2 max-w-[70ch] text-[16px] text-ink/80">
            &ldquo;<Highlight text={it.evidence} />&rdquo;
          </blockquote>
        )}
        {facts.length > 0 && (
          <dl className="mt-3 flex flex-wrap gap-x-7 gap-y-2">
            {facts.map(([k, v, isNum]) => (
              <div key={k}>
                <dt className="text-sm text-soft">{k}</dt>
                <dd className={`text-[16px] font-medium ${isNum ? "num" : ""}`}>{v}</dd>
              </div>
            ))}
          </dl>
        )}
        <div className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-2">
          <span className="text-sm text-soft">Your options on WhatsApp</span>
          <Options options={p.options} />
        </div>
      </div>
    </div>
  );
}

/** The owner's WhatsApp buttons: candidate order ids, "new", and always a "no". */
function Options({ options }: { options: unknown }) {
  const opts = (Array.isArray(options) ? options : [])
    .map((o) => (typeof o === "object" && o !== null ? ((o as Record<string, unknown>).order_id ?? (o as Record<string, unknown>).id) : o))
    .filter((o): o is number | string => typeof o === "number" || typeof o === "string")
    .slice(0, 2);
  const btn = "inline-flex items-center rounded-full border px-3.5 py-1 text-sm font-medium";
  return (
    <div className="flex flex-wrap gap-2">
      {opts.map((o) =>
        String(o) === "new" ? (
          <span key="new" className={`${btn} border-ink/35`}>
            Naya order
          </span>
        ) : /^\d+$/.test(String(o)) ? (
          <Link
            key={o}
            href={`/orders/${o}`}
            className={`${btn} border-ink/35 transition-colors duration-150 hover:border-ink hover:bg-paper-2`}
            title={`Open order #${o}`}
          >
            Order <span className="num ml-1">#{o}</span>
          </Link>
        ) : null,
      )}
      <span className={`${btn} border-ink/20 text-soft`}>Nahi</span>
    </div>
  );
}
