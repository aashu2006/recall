import Link from "next/link";
import { Badge, Card, Empty, PageTitle } from "@/components/ui";
import { fmtDate, fmtNum, fmtRate, istDate } from "@/lib/format";
import { db, must } from "@/lib/supabase";
import type { Order } from "@/lib/types";

export const dynamic = "force-dynamic";

async function load() {
  const [orders, pending] = await Promise.all([
    db()
      .from("orders")
      .select("*, clients(name)")
      .eq("status", "open")
      .order("delivery_date", { ascending: true, nullsFirst: false })
      .order("created_at", { ascending: true })
      .limit(500),
    db().from("pending_confirmations").select("id", { count: "exact", head: true }).eq("status", "pending"),
  ]);
  if (pending.error) throw new Error(pending.error.message);
  return { orders: must<Order[]>(orders), pendingCount: pending.count ?? 0 };
}

export default async function Home() {
  const { orders, pendingCount } = await load();
  const today = istDate(0);
  const tomorrow = istDate(1);
  const dueToday = orders.filter((o) => o.delivery_date === today);
  const dueTomorrow = orders.filter((o) => o.delivery_date === tomorrow);
  const overdue = orders.filter((o) => o.delivery_date && o.delivery_date < today).length;

  return (
    <>
      <PageTitle sub={`${fmtDate(today)} · ${orders.length} open orders${overdue ? ` · ${overdue} overdue` : ""}`}>
        Order book
      </PageTitle>

      <div className="grid gap-3 sm:grid-cols-3">
        <DeliveryCard title="Today" date={today} orders={dueToday} />
        <DeliveryCard title="Tomorrow" date={tomorrow} orders={dueTomorrow} />
        <Link
          href="/pending"
          className={`flex flex-col justify-between rounded-xl border p-4 transition-colors ${
            pendingCount
              ? "border-amber-500/40 bg-amber-500/10 hover:bg-amber-500/15"
              : "border-line bg-surface hover:bg-line/30"
          }`}
        >
          <span className="text-sm font-medium text-muted">Pending confirmations</span>
          <span className="mt-2 text-3xl font-semibold tabular-nums">{pendingCount}</span>
          <span className="mt-1 text-xs text-muted">{pendingCount ? "Waiting for owner's tap →" : "Nothing to confirm"}</span>
        </Link>
      </div>

      <h2 className="mt-8 mb-3 text-sm font-semibold uppercase tracking-wide text-muted">Open orders</h2>
      <Card>{orders.length ? <OrdersTable orders={orders} today={today} /> : <Empty>No open orders yet.</Empty>}</Card>
    </>
  );
}

function DeliveryCard({ title, date, orders }: { title: string; date: string; orders: Order[] }) {
  return (
    <Card className="p-4">
      <div className="flex items-baseline justify-between">
        <span className="text-sm font-medium text-muted">Deliveries {title.toLowerCase()}</span>
        <span className="text-xs text-muted">{fmtDate(date)}</span>
      </div>
      <span className="mt-2 block text-3xl font-semibold tabular-nums">{orders.length}</span>
      {orders.length > 0 && (
        <ul className="mt-3 space-y-1.5 border-t border-line pt-3 text-sm">
          {orders.map((o) => (
            <li key={o.id}>
              <Link href={`/orders/${o.id}`} className="flex justify-between gap-2 hover:text-accent">
                <span className="truncate">
                  {o.clients?.name ?? "Unknown"} · {o.item}
                </span>
                <span className="shrink-0 tabular-nums text-muted">
                  {fmtNum(o.quantity)} {o.unit}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function OrdersTable({ orders, today }: { orders: Order[]; today: string }) {
  const overdue = (o: Order) => o.status === "open" && !!o.delivery_date && o.delivery_date < today;
  return (
    <>
      {/* Phones: one card per order */}
      <ul className="divide-y divide-line sm:hidden">
        {orders.map((o) => (
          <li key={o.id}>
            <Link href={`/orders/${o.id}`} className="block px-4 py-3 active:bg-line/40">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="truncate font-medium">
                    {o.item} {o.spec && <span className="font-normal text-muted">· {o.spec}</span>}
                  </p>
                  <p className="truncate text-sm text-muted">{o.clients?.name ?? "Unknown client"}</p>
                </div>
                <Badge status={overdue(o) ? "overdue" : o.status} />
              </div>
              <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm tabular-nums">
                <span>
                  {fmtNum(o.quantity)} {o.unit}
                </span>
                <span>{fmtRate(o.rate, o.unit)}</span>
                <span className="text-muted">Due {fmtDate(o.delivery_date)}</span>
              </div>
            </Link>
          </li>
        ))}
      </ul>

      {/* Tablets and up: table */}
      <div className="hidden overflow-x-auto sm:block">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-muted">
              <th className="px-4 py-2.5 font-medium">Client</th>
              <th className="px-3 py-2.5 font-medium">Item</th>
              <th className="px-3 py-2.5 font-medium">Spec</th>
              <th className="px-3 py-2.5 text-right font-medium">Qty</th>
              <th className="px-3 py-2.5 font-medium">Unit</th>
              <th className="px-3 py-2.5 text-right font-medium">Rate</th>
              <th className="px-3 py-2.5 font-medium">Delivery</th>
              <th className="px-4 py-2.5 font-medium">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {orders.map((o) => (
              <tr key={o.id} className="group hover:bg-line/30">
                <td className="px-4 py-2.5">
                  <Link href={`/orders/${o.id}`} className="font-medium group-hover:text-accent">
                    {o.clients?.name ?? "Unknown"}
                  </Link>
                </td>
                <td className="px-3 py-2.5">
                  <Link href={`/orders/${o.id}`}>{o.item}</Link>
                </td>
                <td className="px-3 py-2.5 text-muted">{o.spec ?? "—"}</td>
                <td className="px-3 py-2.5 text-right tabular-nums">{fmtNum(o.quantity)}</td>
                <td className="px-3 py-2.5 text-muted">{o.unit ?? "—"}</td>
                <td className="px-3 py-2.5 text-right tabular-nums">{fmtRate(o.rate)}</td>
                <td className={`px-3 py-2.5 whitespace-nowrap ${overdue(o) ? "text-red-600 dark:text-red-400" : ""}`}>
                  {fmtDate(o.delivery_date)}
                </td>
                <td className="px-4 py-2.5">
                  <Badge status={overdue(o) ? "overdue" : o.status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
