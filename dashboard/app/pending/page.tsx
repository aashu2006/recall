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
      <PageTitle
        sub="When Recall isn't sure, it asks you on WhatsApp instead of guessing. Nothing is saved until you tap an answer."
      >
        Waiting for your answer
      </PageTitle>
      <Register>
        {items.length === 0 ? (
          <Empty icon="check">All clear. Nothing is waiting for you.</Empty>
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
    <div className="grid gap-x-10 gap-y-4 px-4 py-6 sm:px-6 md:grid-cols-[250px_1fr]">
      <div className="min-w-0">
        <p className="text-[17px] font-medium">{p.clients?.name ?? "Unknown client"}</p>
        <p className="num mt-0.5 text-sm text-soft">
          {fmtTime(p.created_at)}
          {p.call_id != null && (
            <>
              <span className="mx-1.5 text-rule">|</span>
              <Link href={`/calls#call-${p.call_id}`} className="rounded underline decoration-rule underline-offset-4 hover:text-ink">
                Call #{p.call_id}
              </Link>
            </>
          )}
        </p>
        <p className="mt-3">
          <Badge status="pending" />
        </p>
      </div>

      <div className="min-w-0">
        <h2 className="max-w-[56ch] font-serif text-[21px] leading-snug font-semibold">{question}</h2>
        {it.evidence && (
          <blockquote lang="hi" className="mt-3 max-w-[68ch] border-l-2 border-rule pl-4 text-[16px] text-ink/85">
            <Highlight text={it.evidence} />
          </blockquote>
        )}
        {facts.length > 0 && (
          <dl className="mt-5 flex flex-wrap gap-x-9 gap-y-3">
            {facts.map(([k, v, isNum]) => (
              <div key={k}>
                <dt className="label">{k}</dt>
                <dd className={`mt-1 text-[17px] font-medium ${isNum ? "num" : ""}`}>{v}</dd>
              </div>
            ))}
          </dl>
        )}
        <div className="mt-6 max-w-md rounded-md border border-rule bg-paper-3 p-3 sm:p-4">
          <p className="label mb-2.5 flex items-center gap-2">
            <ChatIcon />
            Your options on WhatsApp
          </p>
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
  const btn =
    "flex min-h-11 flex-1 basis-28 items-center justify-center rounded-md border bg-paper px-3 py-2 text-[15px] font-medium";
  return (
    <div className="flex flex-wrap gap-2">
      {opts.map((o) =>
        String(o) === "new" ? (
          <span key="new" className={`${btn} border-ink/25 text-ink`}>
            Naya order
          </span>
        ) : /^\d+$/.test(String(o)) ? (
          <Link
            key={o}
            href={`/orders/${o}`}
            className={`${btn} border-ink/25 text-ink transition-colors duration-150 hover:border-ink hover:bg-paper-2`}
            title={`Open order #${o}`}
          >
            Order <span className="num ml-1">#{o}</span>
          </Link>
        ) : null,
      )}
      <span className={`${btn} border-ink/15 text-soft`}>Nahi</span>
    </div>
  );
}

function ChatIcon() {
  return (
    <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden>
      <path d="M2.5 3.5h11v7.5h-6L4.5 13.5V11h-2V3.5Z" strokeLinejoin="round" />
    </svg>
  );
}
