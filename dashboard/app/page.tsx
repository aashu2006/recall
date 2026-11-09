import Link from "next/link";
import { Badge, Card, Empty, PageTitle, SectionTitle, StatStrip } from "@/components/ui";
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

/** Changes whenever the order does, so the row remounts and fades in after a refresh. */
const rowKey = (o: Order) => `${o.id}-${o.updated_at}`;

export default async function Home() {
  const { orders, pendingCount } = await load();
  const today = istDate(0);
  const tomorrow = istDate(1);
  const dueToday = orders.filter((o) => o.delivery_date === today);
  const dueTomorrow = orders.filter((o) => o.delivery_date === tomorrow);
  const overdue = orders.filter((o) => o.delivery_date && o.delivery_date < today).length;
  const clients = new Set(orders.map((o) => o.client_id)).size;

  return (
    <>
      <PageTitle sub={fmtDate(today, true)}>Order book</PageTitle>

      <StatStrip
        stats={[
          { label: "Open orders", value: orders.length, note: `${clients} ${clients === 1 ? "client" : "clients"}` },
          {
            label: "Deliveries today",
            value: dueToday.length,
            note: overdue ? `${overdue} overdue from earlier` : fmtDate(today),
          },
          { label: "Deliveries tomorrow", value: dueTomorrow.length, note: fmtDate(tomorrow) },
          {
            label: "Needs your answer",
            value: pendingCount,
            note: pendingCount ? "Answer on WhatsApp" : "Nothing to confirm",
            href: "/pending",
            alert: pendingCount > 0,
          },
        ]}
      />

      <div className="mt-10 grid gap-8 lg:grid-cols-2 lg:gap-6">
        <DeliveryDay title="Today" date={today} orders={dueToday} />
        <DeliveryDay title="Tomorrow" date={tomorrow} orders={dueTomorrow} />
      </div>

      <div className="mt-10">
        <SectionTitle aside={`${orders.length} open`}>All open orders</SectionTitle>
        <Card>{orders.length ? <OrdersTable orders={orders} today={today} /> : <Empty>No open orders yet.</Empty>}</Card>
      </div>
    </>
  );
}

function DeliveryDay({ title, date, orders }: { title: string; date: string; orders: Order[] }) {
  return (
    <section>
      <SectionTitle aside={fmtDate(date)}>Deliver {title.toLowerCase()}</SectionTitle>
      {orders.length === 0 ? (
        <Card>
          <Empty>Nothing due {title.toLowerCase()}.</Empty>
        </Card>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2">
          {orders.map((o) => (
            <li key={rowKey(o)} className="fresh">
              <JobCard order={o} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

/** A delivery as a job card: who, what, how much. */
function JobCard({ order: o }: { order: Order }) {
  return (
    <Link
      href={`/orders/${o.id}`}
      className="group flex h-full flex-col rounded-xl border border-line bg-surface p-4 transition-colors duration-150 hover:border-accent/60 hover:bg-raised/50"
    >
      <span className="truncate text-sm text-muted">{o.clients?.name ?? "Unknown client"}</span>
      <span className="mt-0.5 truncate text-[17px] font-semibold">
        {o.item}
        {o.spec && <span className="font-normal text-muted"> {o.spec}</span>}
      </span>
      <span className="mt-auto flex items-baseline justify-between gap-3 pt-4">
        <span className="text-[26px] leading-none font-semibold tracking-tight">
          {fmtNum(o.quantity)}
          <span className="ml-1 text-sm font-normal text-muted">{o.unit}</span>
        </span>
        <span className="text-sm text-muted">{fmtRate(o.rate, o.unit)}</span>
      </span>
    </Link>
  );
}

function OrdersTable({ orders, today }: { orders: Order[]; today: string }) {
  const overdue = (o: Order) => o.status === "open" && !!o.delivery_date && o.delivery_date < today;
  const dueLabel = (o: Order) =>
    o.delivery_date === today ? "Today" : o.delivery_date === istDate(1) ? "Tomorrow" : fmtDate(o.delivery_date);
  return (
    <>
      {/* Phones: one row per order */}
      <ul className="divide-y divide-line sm:hidden">
        {orders.map((o) => (
          <li key={rowKey(o)} className="fresh">
            <Link href={`/orders/${o.id}`} className="block px-4 py-3.5 active:bg-raised">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate font-medium">
                    {o.item} {o.spec && <span className="font-normal text-muted">{o.spec}</span>}
                  </p>
                  <p className="truncate text-sm text-muted">{o.clients?.name ?? "Unknown client"}</p>
                </div>
                <div className="text-right">
                  <p className="font-semibold">
                    {fmtNum(o.quantity)} <span className="text-sm font-normal text-muted">{o.unit}</span>
                  </p>
                  <p className="text-sm text-muted">{fmtRate(o.rate, o.unit)}</p>
                </div>
              </div>
              <p className={`mt-1.5 text-sm ${overdue(o) ? "text-was" : "text-muted"}`}>
                {overdue(o) ? "Overdue, was due " : "Due "}
                {dueLabel(o).replace(/^(Today|Tomorrow)$/, (d) => d.toLowerCase())}
              </p>
            </Link>
          </li>
        ))}
      </ul>

      {/* Tablets and up: table */}
      <div className="hidden overflow-x-auto sm:block">
        <table className="w-full text-left text-[15px]">
          <thead>
            <tr className="border-b border-line text-sm text-muted">
              <th className="px-5 py-3 font-medium">Client</th>
              <th className="px-3 py-3 font-medium">Item</th>
              <th className="px-3 py-3 text-right font-medium">Quantity</th>
              <th className="px-3 py-3 text-right font-medium">Rate</th>
              <th className="px-3 py-3 font-medium">Delivery</th>
              <th className="px-5 py-3 font-medium">
                <span className="sr-only">Status</span>
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {orders.map((o) => (
              <tr key={rowKey(o)} className="fresh group relative transition-colors duration-150 hover:bg-raised/60">
                <td className="px-5 py-3">
                  {/* The stretched link makes the whole row clickable. */}
                  <Link href={`/orders/${o.id}`} className="font-medium after:absolute after:inset-0 group-hover:text-accent">
                    {o.clients?.name ?? "Unknown"}
                  </Link>
                </td>
                <td className="px-3 py-3">
                  {o.item}
                  {o.spec && <span className="ml-1.5 text-muted">{o.spec}</span>}
                </td>
                <td className="px-3 py-3 text-right whitespace-nowrap">
                  <span className="font-medium">{fmtNum(o.quantity)}</span>
                  <span className="ml-1 text-sm text-muted">{o.unit ?? ""}</span>
                </td>
                <td className="px-3 py-3 text-right whitespace-nowrap">{fmtRate(o.rate)}</td>
                <td className={`px-3 py-3 whitespace-nowrap ${overdue(o) ? "text-was" : ""}`}>{dueLabel(o)}</td>
                <td className="px-5 py-3 text-right">{overdue(o) && <Badge status="overdue" />}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
