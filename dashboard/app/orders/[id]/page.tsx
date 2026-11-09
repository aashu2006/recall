import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import AudioPlayer from "@/components/AudioPlayer";
import { Empty } from "@/components/common";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { signAudio } from "@/lib/audio";
import { fieldLabel, fmtChangeValue, fmtDate, fmtNum, fmtRate, fmtTime, manualLabel } from "@/lib/format";
import { Highlight } from "@/lib/highlight";
import { db, must } from "@/lib/supabase";
import type { Order, OrderChange, Segment } from "@/lib/types";

export const dynamic = "force-dynamic";

type Params = { params: Promise<{ id: string }> };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  return { title: `Order #${(await params).id}` };
}

const STATUS_LABEL: Record<string, string> = { open: "Open", delivered: "Delivered", cancelled: "Cancelled" };

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
      <nav className="mb-3 text-[13px] text-muted-foreground">
        <Link href="/" className="hover:text-foreground">
          Orders
        </Link>
        <span className="mx-1.5">/</span>
        <span className="num">#{order.id}</span>
      </nav>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <h1 className="text-xl font-semibold tracking-tight">{client}</h1>
        <Badge variant="outline">{STATUS_LABEL[order.status] ?? order.status}</Badge>
      </div>
      <dl className="mt-3 flex flex-wrap gap-x-8 gap-y-2">
        <Fact label="Item">
          {order.item}
          {order.spec && <span className="text-muted-foreground"> {order.spec}</span>}
        </Fact>
        <Fact label="Qty">
          <span className="num">{fmtNum(order.quantity)}</span>
          {order.unit && <span className="text-muted-foreground"> {order.unit}</span>}
        </Fact>
        <Fact label="Rate">
          <span className="num">{fmtRate(order.rate, order.unit)}</span>
        </Fact>
        <Fact label="Due">{fmtDate(order.delivery_date)}</Fact>
      </dl>

      <h2 className="mt-10 mb-3 font-medium">
        Changes <span className="num ml-1 font-normal text-muted-foreground">{changes.length}</span>
      </h2>
      <Card className="gap-0 py-0">
        {events.length === 0 ? (
          <Empty>No changes recorded.</Empty>
        ) : (
          <ol className="divide-y">
            {events.map((e) => (
              <li key={e.key}>
                <Entry event={e} audio={e.audioUrl ? (signed.get(e.audioUrl) ?? null) : null} unit={order.unit} />
              </li>
            ))}
          </ol>
        )}
      </Card>
    </>
  );
}

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline gap-2">
      <dt className="text-[13px] text-muted-foreground">{label}</dt>
      <dd>{children}</dd>
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

/** One voice note (or manual edit): the fields it changed, when, and the clip that proves it. */
function Entry({ event: e, audio, unit }: { event: ChangeEvent; audio: string | null; unit: string | null }) {
  const fromCall = e.callId != null;
  const created = e.changes.find((c) => c.field === "created");
  const edits = e.changes.filter((c) => c.field !== "created");
  const said = fromCall ? evidence(e) : null;

  return (
    <div className="px-4 py-4">
      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-1">
        <dl className="grid min-w-0 grid-cols-[110px_1fr] gap-x-4 gap-y-1.5">
          {created && (
            <>
              <dt className="text-muted-foreground">Created</dt>
              <dd>{createdSummary(created.new_value)}</dd>
            </>
          )}
          {edits.map((c) => (
            <ChangeRow key={c.id} change={c} unit={unit} />
          ))}
        </dl>
        <p className="text-[13px] text-muted-foreground">
          <span className="tabular-nums">{fmtTime(e.createdAt)}</span>
          <span className="mx-1.5">·</span>
          {fromCall ? (
            <Link href={`/calls#call-${e.callId}`} className="hover:text-foreground">
              Call <span className="num">#{e.callId}</span>
            </Link>
          ) : (
            manualLabel(created ? "created" : e.changes[0].field)
          )}
        </p>
      </div>

      {fromCall && (
        <div className="mt-3">
          <AudioPlayer src={audio} start={e.clipStart} end={e.clipEnd} />
          {said && (
            <p lang="hi" className="mt-1.5 max-w-prose text-[13px] text-muted-foreground">
              &ldquo;
              <Highlight text={said} />
              &rdquo;
            </p>
          )}
        </div>
      )}
    </div>
  );
}

/** "Quantity   200 → 300 kg": old value muted and struck through. */
function ChangeRow({ change: c, unit }: { change: OrderChange; unit: string | null }) {
  const numeric = ["quantity", "rate", "delivery_date"].includes(c.field) ? "num" : "";
  const qtyUnit = c.field === "quantity" && unit ? ` ${unit}` : "";
  return (
    <>
      <dt className="text-muted-foreground">{fieldLabel(c.field)}</dt>
      <dd>
        {c.old_value != null && c.old_value !== "" && (
          <>
            <span className={`${numeric} text-muted-foreground line-through`}>{fmtChangeValue(c.field, c.old_value)}</span>
            <span className="mx-2 text-muted-foreground">→</span>
          </>
        )}
        <span className={numeric}>{fmtChangeValue(c.field, c.new_value)}</span>
        {qtyUnit && <span className="text-muted-foreground">{qtyUnit}</span>}
      </dd>
    </>
  );
}

/** new_value of a "created" row is either a JSON snapshot of the order or plain text. */
function createdSummary(value: string | null): string {
  let obj: Record<string, unknown> | null = null;
  try {
    const parsed = value ? JSON.parse(value) : null;
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) obj = parsed;
  } catch {}
  if (!obj) return value ?? "—";

  const unit = typeof obj.unit === "string" ? obj.unit : null;
  return Object.entries(obj)
    .filter(
      ([k, v]) =>
        v !== null &&
        v !== "" &&
        !["id", "client_id", "created_at", "updated_at", "status"].includes(k) &&
        !(k === "unit" && obj!.quantity != null),
    )
    .sort(([a], [b]) => fieldRank(a) - fieldRank(b))
    .map(([k, v]) => {
      const s = fmtChangeValue(k, String(v));
      if (k === "quantity" && unit) return `${s} ${unit}`;
      if (k === "delivery_date") return `due ${s}`;
      return s;
    })
    .join(" · ");
}
