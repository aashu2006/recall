import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import AudioPlayer from "@/components/AudioPlayer";
import { Badge, Card, Empty, SectionTitle } from "@/components/ui";
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
      <Link href="/" className="inline-flex items-center gap-1.5 rounded text-sm text-muted transition-colors hover:text-ink">
        <svg viewBox="0 0 16 16" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
          <path d="M10 3.5 5.5 8l4.5 4.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        Order book
      </Link>

      <div className="mt-4 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm text-muted">
            {client}, order #{order.id}
          </p>
          <h1 className="mt-0.5 text-[26px] font-semibold tracking-tight sm:text-[34px]">
            {order.item}
            {order.spec && <span className="font-normal text-muted"> {order.spec}</span>}
          </h1>
        </div>
        <Badge status={order.status} />
      </div>

      <dl key={order.updated_at} className="fresh mt-5 grid grid-cols-2 gap-x-6 gap-y-4 border-y border-line py-4 sm:grid-cols-4">
        <Fact label="Quantity" value={`${fmtNum(order.quantity)} ${order.unit ?? ""}`} />
        <Fact label="Rate" value={fmtRate(order.rate, order.unit)} />
        <Fact label="Delivery" value={fmtDate(order.delivery_date)} />
        <Fact label="Last changed" value={fmtTime(order.updated_at)} />
      </dl>

      <div className="mt-10">
        <SectionTitle aside={`${changes.length} ${changes.length === 1 ? "entry" : "entries"}`}>
          What changed, and who said it
        </SectionTitle>
        {events.length === 0 ? (
          <Card>
            <Empty>No changes recorded.</Empty>
          </Card>
        ) : (
          <ol className="space-y-4">
            {events.map((e, i) => (
              <li key={e.key} className="fresh">
                <EventCard
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
      </div>
    </>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-sm text-muted">{label}</dt>
      <dd className="mt-0.5 text-[17px] font-semibold">{value}</dd>
    </div>
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

/** One voice note can change several fields at once (quantity and rate): show them as one event. */
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
  // Same field order in every event, the way the owner reads an order.
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

function EventCard({
  event: e,
  client,
  latest,
  audio,
  unit,
}: {
  event: ChangeEvent;
  client: string;
  unit: string | null;
  latest: boolean;
  audio: string | null;
}) {
  const fromCall = e.callId != null;
  const created = e.changes.find((c) => c.field === "created");
  const edits = e.changes.filter((c) => c.field !== "created");
  const said = fromCall ? evidence(e) : null;

  return (
    <Card className={`overflow-hidden ${latest ? "border-accent/45" : ""}`}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 px-4 pt-4 sm:px-5">
        <p className="font-medium">
          {created ? (fromCall ? "New order from a voice note" : manualLabel("created")) : fromCall ? "Updated from a voice note" : manualLabel(e.changes[0].field)}
          {latest && <span className="ml-2 text-sm font-normal text-accent">Latest</span>}
        </p>
        <p className="text-sm text-muted">
          {fmtTime(e.createdAt)}
          {e.confidence != null && fromCall && <span> · {Math.round(e.confidence * 100)}% sure</span>}
        </p>
      </div>

      <div className="px-4 pt-3 pb-4 sm:px-5">
        {created && <CreatedValue value={created.new_value} />}
        {edits.length > 0 && (
          <dl className="divide-y divide-line/70">
            {edits.map((c) => (
              <Diff key={c.id} change={c} unit={unit} />
            ))}
          </dl>
        )}
      </div>

      {fromCall && (
        <div className="grid gap-4 border-t border-line bg-raised/50 px-4 py-4 sm:px-5 md:grid-cols-[minmax(240px,320px)_1fr] md:gap-6">
          <AudioPlayer
            src={audio}
            start={e.clipStart}
            end={e.clipEnd}
            size="lg"
            label={e.clipStart != null ? `${client} saying it` : `${client}'s voice note`}
          />
          <div className="min-w-0">
            {said ? (
              <blockquote lang="hi" className="border-l-2 border-accent/60 pl-4 text-[17px] text-ink">
                &ldquo;<Highlight text={said} />&rdquo;
              </blockquote>
            ) : (
              <p className="text-sm text-muted">No transcript lines for this clip.</p>
            )}
            <Link
              href={`/calls#call-${e.callId}`}
              className="mt-2 inline-block rounded text-sm text-muted underline decoration-line underline-offset-4 transition-colors hover:text-ink hover:decoration-muted"
            >
              Full transcript of call #{e.callId}
            </Link>
          </div>
        </div>
      )}
    </Card>
  );
}

function Diff({ change: c, unit }: { change: OrderChange; unit: string | null }) {
  const qtyUnit = c.field === "quantity" && unit ? unit : null;
  const delta = fmtDelta(c.field, c.old_value, c.new_value);
  return (
    <div className="grid grid-cols-[minmax(84px,auto)_1fr] items-baseline gap-x-4 py-2.5 first:pt-0 last:pb-0 sm:grid-cols-[120px_1fr]">
      <dt className="text-sm text-muted">{fieldLabel(c.field)}</dt>
      <dd className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="text-[17px] text-was line-through decoration-was/50 decoration-[1.5px]">
          {fmtChangeValue(c.field, c.old_value)}
        </span>
        <svg viewBox="0 0 20 12" className="h-3 w-5 self-center text-muted" fill="none" stroke="currentColor" strokeWidth="1.6" aria-label="changed to">
          <path d="M1 6h17M13 1.5 18 6l-5 4.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <span className="text-[28px] leading-tight font-semibold tracking-tight text-now sm:text-[32px]">
          {fmtChangeValue(c.field, c.new_value)}
          {qtyUnit && <span className="ml-1.5 text-base font-normal text-muted">{qtyUnit}</span>}
        </span>
        {delta && <span className="rounded-full border border-line px-2 py-0.5 text-sm text-muted">{delta}</span>}
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
  if (!obj) return value ? <p className="text-[15px]">{value}</p> : null;

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
    <dl className="flex flex-wrap gap-2">
      {entries.map(([k, v]) => (
        <div key={k} className="rounded-lg border border-line px-3 py-1.5">
          <dt className="text-xs text-muted">{fieldLabel(k)}</dt>
          <dd className="font-medium">{v}</dd>
        </div>
      ))}
    </dl>
  );
}
