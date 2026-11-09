import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import AudioPlayer from "@/components/AudioPlayer";
import { Badge, Empty, Register, SectionTitle, SummaryRow, Unit } from "@/components/ui";
import { signAudio } from "@/lib/audio";
import {
  fieldLabel,
  fmtChangeValue,
  fmtDate,
  fmtDelta,
  fmtNum,
  fmtRate,
  fmtTime,
  manualLabel,
  TZ,
} from "@/lib/format";
import { Highlight } from "@/lib/highlight";
import { db, must } from "@/lib/supabase";
import type { Order, OrderChange, Segment } from "@/lib/types";

export const dynamic = "force-dynamic";

type Params = { params: Promise<{ id: string }> };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  return { title: `Order #${(await params).id}` };
}

export default async function OrderPage({ params }: Params) {
  const { id } = await params;
  if (!/^\d+$/.test(id)) notFound();

  const [orderRes, changesRes] = await Promise.all([
    db().from("orders").select("*, clients(name)").eq("id", id).maybeSingle(),
    db()
      .from("order_changes")
      .select("*, calls(audio_url, segments)")
      .eq("order_id", id)
      .order("created_at", { ascending: false })
      .order("id", { ascending: false }),
  ]);
  const order = must<Order | null>(orderRes);
  if (!order) notFound();
  const changes = must<OrderChange[]>(changesRes);
  const signed = await signAudio(changes.map((c) => c.calls?.audio_url ?? null));
  const events = groupEvents(changes);
  const client = order.clients?.name ?? "Unknown client";

  return (
    <>
      <Link href="/" className="inline-flex items-center gap-1.5 rounded text-sm text-soft transition-colors hover:text-ink">
        <svg viewBox="0 0 16 16" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
          <path d="M10 3.5 5.5 8l4.5 4.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        Order book
      </Link>

      <div className="mt-5 mb-8 flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
        <div className="min-w-0">
          <p className="text-[15px] text-soft">
            <span className="font-medium text-ink">{client}</span>
            <span className="mx-2 text-rule">|</span>
            <span className="num">Order #{order.id}</span>
          </p>
          <h1 className="mt-2 font-serif text-[34px] leading-[1.05] font-semibold tracking-tight sm:text-[48px]">
            {order.item}
            {order.spec && <span className="font-medium text-soft"> {order.spec}</span>}
          </h1>
        </div>
        <Badge status={order.status} />
      </div>

      <div key={order.updated_at} className="fresh">
        <SummaryRow
          size="md"
          stats={[
            {
              label: "Quantity",
              value: (
                <>
                  {fmtNum(order.quantity)}
                  {order.unit && <Unit>{order.unit}</Unit>}
                </>
              ),
            },
            {
              label: "Rate",
              value: order.rate == null ? "—" : (
                <>
                  {fmtRate(order.rate)}
                  {order.unit && <span className="text-[0.62em] font-normal text-soft">/{order.unit}</span>}
                </>
              ),
            },
            { label: "Delivery", value: fmtDate(order.delivery_date) },
            { label: "Last changed", value: fmtTime(order.updated_at) },
          ]}
        />
      </div>

      <div className="mt-14">
        <SectionTitle aside={<span className="num">{changes.length} {changes.length === 1 ? "entry" : "entries"}</span>}>
          What changed, and who said it
        </SectionTitle>
        <Register>
          {events.length === 0 ? (
            <Empty>No changes recorded.</Empty>
          ) : (
            <ol className="divide-y divide-rule">
              {events.map((e, i) => (
                <li key={e.key} className="fresh">
                  <Entry
                    event={e}
                    client={client}
                    latest={i === 0 && events.length > 1}
                    audio={e.audioUrl ? (signed.get(e.audioUrl) ?? null) : null}
                    unit={order.unit}
                  />
                </li>
              ))}
            </ol>
          )}
        </Register>
      </div>
    </>
  );
}

interface ChangeEvent {
  key: string;
  callId: number | null;
  createdAt: string;
  audioUrl: string | null;
  segments: Segment[];
  clipStart: number | null;
  clipEnd: number | null;
  confidence: number | null;
  changes: OrderChange[];
}

/** One voice note can change several fields at once (quantity and rate): show them as one entry. */
function groupEvents(changes: OrderChange[]): ChangeEvent[] {
  const events = new Map<string, ChangeEvent>();
  for (const c of changes) {
    const key = [c.call_id ?? "manual", c.clip_start, c.clip_end, c.created_at.slice(0, 19)].join("|");
    let e = events.get(key);
    if (!e) {
      e = {
        key: `${key}|${c.id}`,
        callId: c.call_id,
        createdAt: c.created_at,
        audioUrl: c.calls?.audio_url ?? null,
        segments: Array.isArray(c.calls?.segments) ? c.calls.segments : [],
        clipStart: c.clip_start != null ? Number(c.clip_start) : null,
        clipEnd: c.clip_end != null ? Number(c.clip_end) : null,
        confidence: c.confidence,
        changes: [],
      };
      events.set(key, e);
    }
    e.changes.push(c);
    if (c.confidence != null) e.confidence = Math.min(e.confidence ?? 1, c.confidence);
  }
  // Same field order in every entry, the way the owner reads an order.
  for (const e of events.values()) e.changes.sort((a, b) => fieldRank(a.field) - fieldRank(b.field) || a.id - b.id);
  return [...events.values()];
}

const FIELD_ORDER = ["created", "item", "spec", "quantity", "unit", "rate", "delivery_date", "status"];
const fieldRank = (f: string) => (FIELD_ORDER.includes(f) ? FIELD_ORDER.indexOf(f) : FIELD_ORDER.length);

/** The transcript lines inside the proof clip. */
function evidence(e: ChangeEvent): string | null {
  if (e.clipStart == null || e.clipEnd == null || !e.segments.length) return null;
  const text = e.segments
    .filter((s) => Number(s.end) > e.clipStart! && Number(s.start) < e.clipEnd!)
    .map((s) => s.text.trim())
    .filter(Boolean)
    .join(" ");
  return text || null;
}

const dayOf = (ts: string) =>
  new Date(ts).toLocaleDateString("en-IN", { timeZone: TZ, day: "numeric", month: "short" });
const timeOf = (ts: string) =>
  new Date(ts).toLocaleTimeString("en-IN", { timeZone: TZ, hour: "numeric", minute: "2-digit", hour12: true });

/** One register entry: when (left column), what changed, and the recording that proves it. */
function Entry({
  event: e,
  client,
  latest,
  audio,
  unit,
}: {
  event: ChangeEvent;
  client: string;
  latest: boolean;
  audio: string | null;
  unit: string | null;
}) {
  const fromCall = e.callId != null;
  const created = e.changes.find((c) => c.field === "created");
  const edits = e.changes.filter((c) => c.field !== "created");
  const said = fromCall ? evidence(e) : null;
  const what = created
    ? fromCall
      ? `New order, from a voice note by ${client}`
      : manualLabel("created")
    : fromCall
      ? `Changed in a voice note by ${client}`
      : manualLabel(e.changes[0].field);

  return (
    <div className={`grid gap-x-8 gap-y-3 px-4 py-6 sm:grid-cols-[92px_1fr] sm:px-6 ${latest ? "bg-paper-3" : ""}`}>
      <div className="num flex items-baseline gap-2 text-sm sm:block sm:pt-0.5">
        <p className="font-medium text-ink">{dayOf(e.createdAt)}</p>
        <p className="text-soft">{timeOf(e.createdAt)}</p>
        {latest && (
          <p className="ml-auto text-[12px] font-semibold tracking-[0.06em] text-red uppercase sm:mt-2 sm:ml-0">Latest</p>
        )}
      </div>

      <div className="min-w-0">
        <p className="flex flex-wrap items-center gap-x-2.5 gap-y-1 text-[15px] text-soft">
          {fromCall ? <MicIcon /> : <PenIcon />}
          <span>{what}</span>
          {e.confidence != null && fromCall && (
            <span className="num rounded-full bg-ink/[0.06] px-2 py-px text-[12px] text-soft">
              {Math.round(e.confidence * 100)}% sure
            </span>
          )}
        </p>

        {created && <CreatedValue value={created.new_value} />}
        {edits.length > 0 && (
          <dl className="mt-4 space-y-3">
            {edits.map((c) => (
              <Diff key={c.id} change={c} unit={unit} />
            ))}
          </dl>
        )}

        {fromCall && (
          <div className="mt-6 grid gap-x-8 gap-y-4 rounded-md border border-rule bg-paper-3 p-4 sm:p-5 lg:grid-cols-[260px_1fr]">
            <div className="lg:border-r lg:border-rule lg:pr-8">
              <p className="label mb-3">Proof</p>
              <AudioPlayer src={audio} start={e.clipStart} end={e.clipEnd} variant="proof" />
            </div>
            <div className="min-w-0">
              {said && (
                <>
                  <p className="label mb-2">What was said</p>
                  <blockquote lang="hi" className="max-w-[68ch] text-[17px] text-ink/85">
                    <span className="text-faint">&ldquo;</span>
                    <Highlight text={said} />
                    <span className="text-faint">&rdquo;</span>
                  </blockquote>
                </>
              )}
              <Link
                href={`/calls#call-${e.callId}`}
                className={`group inline-block rounded text-sm text-soft transition-colors hover:text-ink ${said ? "mt-3" : ""}`}
              >
                <span className="underline decoration-rule underline-offset-4 group-hover:decoration-ink/40">
                  Full transcript of call <span className="num">#{e.callId}</span>
                </span>
                <span aria-hidden className="ml-1 inline-block transition-transform group-hover:translate-x-0.5">
                  →
                </span>
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/** Old value struck through in red ink, an arrow, the new value written large in ink. */
function Diff({ change: c, unit }: { change: OrderChange; unit: string | null }) {
  const delta = fmtDelta(c.field, c.old_value, c.new_value);
  const qtyUnit = c.field === "quantity" && unit ? unit : null;
  return (
    <div className="grid grid-cols-[84px_1fr] items-baseline gap-x-3 sm:grid-cols-[108px_1fr]">
      <dt className="label">{fieldLabel(c.field)}</dt>
      <dd className="num flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="text-[18px] text-red/90 line-through decoration-red decoration-[1.5px]">
          {fmtChangeValue(c.field, c.old_value)}
        </span>
        <svg viewBox="0 0 20 12" className="h-3 w-5 shrink-0 self-center text-faint" fill="none" stroke="currentColor" strokeWidth="1.6" aria-label="changed to">
          <path d="M1 6h17M13 1.5 18 6l-5 4.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <span className="text-[30px] leading-none font-medium tracking-tight text-ink sm:text-[36px]">
          {fmtChangeValue(c.field, c.new_value)}
          {qtyUnit && <Unit>{qtyUnit}</Unit>}
        </span>
        {delta && <span className="rounded bg-ink/[0.06] px-1.5 py-px text-[13px] text-soft">{delta}</span>}
      </dd>
    </div>
  );
}

/** new_value of a "created" row is either a JSON snapshot of the order or plain text. */
function CreatedValue({ value }: { value: string | null }) {
  let obj: Record<string, unknown> | null = null;
  try {
    const parsed = value ? JSON.parse(value) : null;
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) obj = parsed;
  } catch {}
  if (!obj) return value ? <p className="mt-3 text-[15px]">{value}</p> : null;

  const unit = typeof obj.unit === "string" ? obj.unit : null;
  const entries = Object.entries(obj)
    .filter(
      ([k, v]) =>
        v !== null &&
        v !== "" &&
        !["id", "client_id", "created_at", "updated_at", "status"].includes(k) &&
        !(k === "unit" && obj!.quantity != null),
    )
    .map(([k, v]): [string, string] => [
      k,
      k === "quantity" && unit ? `${fmtChangeValue(k, String(v))} ${unit}` : fmtChangeValue(k, String(v)),
    ])
    .sort(([a], [b]) => fieldRank(a) - fieldRank(b));
  return (
    <dl className="mt-4 flex flex-wrap gap-x-9 gap-y-3">
      {entries.map(([k, v]) => (
        <div key={k}>
          <dt className="label">{fieldLabel(k)}</dt>
          <dd className={`mt-1 text-[18px] font-medium ${["quantity", "rate", "delivery_date"].includes(k) ? "num" : ""}`}>{v}</dd>
        </div>
      ))}
    </dl>
  );
}

function MicIcon() {
  return (
    <svg viewBox="0 0 16 16" className="h-4 w-4 text-ink" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden>
      <rect x="5.5" y="1.75" width="5" height="8" rx="2.5" />
      <path d="M3 7.5a5 5 0 0 0 10 0M8 12.5v2" strokeLinecap="round" />
    </svg>
  );
}

function PenIcon() {
  return (
    <svg viewBox="0 0 16 16" className="h-4 w-4 text-faint" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden>
      <path d="M10.5 2.5 13.5 5.5 6 13H3v-3l7.5-7.5Z" strokeLinejoin="round" />
    </svg>
  );
}
