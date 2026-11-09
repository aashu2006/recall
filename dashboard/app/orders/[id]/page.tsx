import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import AudioPlayer from "@/components/AudioPlayer";
import { Badge, Card, Empty } from "@/components/ui";
import { signAudio } from "@/lib/audio";
import { fieldLabel, fmtChangeValue, fmtDate, fmtNum, fmtRate, fmtSecs, fmtTime } from "@/lib/format";
import { db, must } from "@/lib/supabase";
import type { Order, OrderChange } from "@/lib/types";

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
      .select("*, calls(audio_url)")
      .eq("order_id", id)
      .order("created_at", { ascending: false })
      .order("id", { ascending: false }),
  ]);
  const order = must<Order | null>(orderRes);
  if (!order) notFound();
  const changes = must<OrderChange[]>(changesRes);
  const signed = await signAudio(changes.map((c) => c.calls?.audio_url ?? null));

  return (
    <>
      <Link href="/" className="text-sm text-muted hover:text-ink">
        ← Order book
      </Link>

      <div className="mt-3 mb-5 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm text-muted">
            #{order.id} · {order.clients?.name ?? "Unknown client"}
          </p>
          <h1 className="text-xl font-semibold tracking-tight">
            {order.item} {order.spec && <span className="font-normal text-muted">· {order.spec}</span>}
          </h1>
        </div>
        <Badge status={order.status} />
      </div>

      <Card className="grid grid-cols-2 gap-px overflow-hidden bg-line sm:grid-cols-4">
        <Stat label="Quantity" value={`${fmtNum(order.quantity)} ${order.unit ?? ""}`} />
        <Stat label="Rate" value={fmtRate(order.rate, order.unit)} />
        <Stat label="Delivery" value={fmtDate(order.delivery_date)} />
        <Stat label="Last change" value={fmtTime(order.updated_at)} />
      </Card>

      <h2 className="mt-8 mb-3 text-sm font-semibold uppercase tracking-wide text-muted">
        Change history · {changes.length}
      </h2>
      {changes.length === 0 ? (
        <Card>
          <Empty>No changes recorded.</Empty>
        </Card>
      ) : (
        <ol className="relative space-y-4 border-l border-line pl-5 ml-2">
          {changes.map((c) => (
            <li key={c.id} className="relative">
              <span
                className={`absolute -left-[27px] top-4 h-3 w-3 rounded-full border-2 border-bg ${
                  c.field === "created" ? "bg-accent" : "bg-muted"
                }`}
              />
              <ChangeCard change={c} audio={c.calls?.audio_url ? signed.get(c.calls.audio_url) ?? null : null} />
            </li>
          ))}
        </ol>
      )}
    </>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-surface p-4">
      <p className="text-xs uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-1 font-medium tabular-nums">{value}</p>
    </div>
  );
}

function ChangeCard({ change: c, audio }: { change: OrderChange; audio: string | null }) {
  const hasClip = c.clip_start != null && c.clip_end != null;
  return (
    <Card className="p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <span className="font-medium">{fieldLabel(c.field)}</span>
        <span className="text-xs text-muted">
          {fmtTime(c.created_at)}
          {c.confidence != null && ` · ${Math.round(c.confidence * 100)}% sure`}
          {c.call_id == null && " · manual edit"}
        </span>
      </div>

      {c.field === "created" ? (
        <CreatedValue value={c.new_value} />
      ) : (
        <p className="mt-2 flex flex-wrap items-center gap-2 text-sm">
          <span className="rounded bg-red-500/10 px-2 py-0.5 text-red-700 line-through decoration-red-400/60 dark:text-red-300">
            {fmtChangeValue(c.field, c.old_value)}
          </span>
          <span className="text-muted">→</span>
          <span className="rounded bg-emerald-500/10 px-2 py-0.5 font-medium text-emerald-700 dark:text-emerald-300">
            {fmtChangeValue(c.field, c.new_value)}
          </span>
        </p>
      )}

      {c.call_id != null && (
        <div className="mt-3 space-y-1">
          <AudioPlayer src={audio} start={c.clip_start} end={c.clip_end} />
          <p className="text-xs text-muted">
            {hasClip ? `Proof clip ${fmtSecs(c.clip_start)}–${fmtSecs(c.clip_end)} of ` : "From "}
            <Link href={`/calls#call-${c.call_id}`} className="underline hover:text-ink">
              call #{c.call_id}
            </Link>
          </p>
        </div>
      )}
    </Card>
  );
}

/** new_value of a "created" row is either a JSON snapshot of the order or plain text. */
function CreatedValue({ value }: { value: string | null }) {
  let obj: Record<string, unknown> | null = null;
  try {
    const parsed = value ? JSON.parse(value) : null;
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) obj = parsed;
  } catch {}
  if (!obj) return value ? <p className="mt-2 text-sm">{value}</p> : null;

  const entries = Object.entries(obj).filter(
    ([k, v]) => v !== null && v !== "" && !["id", "client_id", "created_at", "updated_at"].includes(k),
  );
  return (
    <dl className="mt-2 flex flex-wrap gap-2 text-sm">
      {entries.map(([k, v]) => (
        <div key={k} className="rounded bg-line/50 px-2 py-0.5">
          <dt className="inline text-muted">{fieldLabel(k)}: </dt>
          <dd className="inline font-medium">{fmtChangeValue(k, String(v))}</dd>
        </div>
      ))}
    </dl>
  );
}
