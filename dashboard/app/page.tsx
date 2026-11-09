import Link from "next/link";
import { Badge, Empty, PageTitle, Register, SectionTitle, SummaryRow } from "@/components/ui";
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

/** Changes whenever the order does, so the entry remounts and fades in after a refresh. */
const rowKey = (o: Order) => `${o.id}-${o.updated_at}`;

export default async function Home() {
  const { orders, pendingCount } = await load();
  const today = istDate(0);
  const tomorrow = istDate(1);
  const dueToday = orders.filter((o) => o.delivery_date === today);
  const dueTomorrow = orders.filter((o) => o.delivery_date === tomorrow);
  const overdue = orders.filter((o) => o.delivery_date && o.delivery_date < today).length;
  const clients = new Set(orders.map((o) => o.client_id)).size;
  const dueLabel = (d: string | null) => (d === today ? "Today" : d === tomorrow ? "Tomorrow" : fmtDate(d));

  return (
    <>
      <PageTitle sub={fmtDate(today, true)}>Order book</PageTitle>

      <SummaryRow
        stats={[
          { label: "Open orders", value: orders.length, note: `${clients} ${clients === 1 ? "client" : "clients"}` },
          {
            label: "Deliveries today",
            value: dueToday.length,
            note: overdue ? `${overdue} overdue from earlier` : fmtDate(today),
            alert: overdue > 0,
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

      <div className="mt-12 grid gap-10 lg:grid-cols-2 lg:gap-8">
        <DeliveryDay title="Deliver today" date={today} orders={dueToday} empty="Nothing due today." />
        <DeliveryDay title="Deliver tomorrow" date={tomorrow} orders={dueTomorrow} empty="Nothing due tomorrow." />
      </div>

      <div className="mt-12">
        <SectionTitle aside={`${orders.length} open`}>All open orders</SectionTitle>
        <Register>
          {orders.length ? <OrdersTable orders={orders} today={today} dueLabel={dueLabel} /> : <Empty>No open orders yet.</Empty>}
        </Register>
      </div>
    </>
  );
}

function DeliveryDay({ title, date, orders, empty }: { title: string; date: string; orders: Order[]; empty: string }) {
  return (
    <section>
      <SectionTitle aside={<span className="num">{fmtDate(date)}</span>}>{title}</SectionTitle>
      <Register>
        {orders.length === 0 ? (
          <Empty>{empty}</Empty>
        ) : (
          <ul className="divide-y divide-rule">
            {orders.map((o) => (
              <li key={rowKey(o)} className="fresh">
                <Link
                  href={`/orders/${o.id}`}
                  className="flex items-baseline justify-between gap-4 px-4 py-3.5 transition-colors duration-150 hover:bg-paper-2/70 sm:px-5"
                >
                  <span className="min-w-0">
                    <span className="block truncate text-[16px] font-medium">
                      {o.item}
                      {o.spec && <span className="font-normal text-soft"> {o.spec}</span>}
                    </span>
                    <span className="block truncate text-sm text-soft">{o.clients?.name ?? "Unknown client"}</span>
                  </span>
                  <span className="shrink-0 text-right">
                    <span className="num block text-[22px] leading-tight">
                      {fmtNum(o.quantity)}
                      <span className="ml-1 font-sans text-sm text-soft">{o.unit}</span>
                    </span>
                    <span className="num block text-[13px] text-soft">{fmtRate(o.rate, o.unit)}</span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Register>
    </section>
  );
}

function OrdersTable({ orders, today, dueLabel }: { orders: Order[]; today: string; dueLabel: (d: string | null) => string }) {
  const overdue = (o: Order) => o.status === "open" && !!o.delivery_date && o.delivery_date < today;
  return (
    <>
      {/* Phones: one ruled entry per order */}
      <ul className="divide-y divide-rule sm:hidden">
        {orders.map((o) => (
          <li key={rowKey(o)} className="fresh">
            <Link href={`/orders/${o.id}`} className="block px-4 py-3.5 active:bg-paper-2">
              <div className="flex items-baseline justify-between gap-3">
                <p className="min-w-0 truncate font-medium">
                  {o.item} {o.spec && <span className="font-normal text-soft">{o.spec}</span>}
                </p>
                <p className="num shrink-0">
                  {fmtNum(o.quantity)} <span className="font-sans text-sm text-soft">{o.unit}</span>
                </p>
              </div>
              <div className="mt-0.5 flex items-baseline justify-between gap-3 text-sm">
                <p className="min-w-0 truncate text-soft">{o.clients?.name ?? "Unknown client"}</p>
                <p className="num shrink-0 text-soft">{fmtRate(o.rate, o.unit)}</p>
              </div>
              <p className={`mt-1 text-sm ${overdue(o) ? "text-red" : "text-soft"}`}>
                {overdue(o) ? "Overdue, was due " : "Due "}
                <span className="num">{dueLabel(o.delivery_date).replace(/^(Today|Tomorrow)$/, (d) => d.toLowerCase())}</span>
              </p>
            </Link>
          </li>
        ))}
      </ul>

      {/* Tablets and up: the register */}
      <div className="hidden overflow-x-auto sm:block">
        <table className="w-full text-left text-[15px]">
          <thead>
            <tr className="border-b-[3px] border-double border-ink/30 text-sm text-soft">
              <th className="px-5 py-2.5 font-medium">Client</th>
              <th className="px-3 py-2.5 font-medium">Item</th>
              <th className="px-3 py-2.5 text-right font-medium">Quantity</th>
              <th className="px-3 py-2.5 text-right font-medium">Rate</th>
              <th className="px-3 py-2.5 font-medium">Delivery</th>
              <th className="px-5 py-2.5 font-medium">
                <span className="sr-only">Status</span>
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-rule">
            {orders.map((o) => (
              <tr key={rowKey(o)} className="fresh group relative transition-colors duration-150 hover:bg-paper-2/70">
                <td className="px-5 py-3">
                  {/* The stretched link makes the whole row clickable. */}
                  <Link
                    href={`/orders/${o.id}`}
                    className="font-medium after:absolute after:inset-0 group-hover:underline group-hover:underline-offset-4"
                  >
                    {o.clients?.name ?? "Unknown"}
                  </Link>
                </td>
                <td className="px-3 py-3">
                  {o.item}
                  {o.spec && <span className="ml-1.5 text-soft">{o.spec}</span>}
                </td>
                <td className="num px-3 py-3 text-right whitespace-nowrap">
                  {fmtNum(o.quantity)}
                  <span className="ml-1 font-sans text-sm text-soft">{o.unit ?? ""}</span>
                </td>
                <td className="num px-3 py-3 text-right whitespace-nowrap">{fmtRate(o.rate)}</td>
                <td className={`num px-3 py-3 whitespace-nowrap ${overdue(o) ? "text-red" : ""}`}>{dueLabel(o.delivery_date)}</td>
                <td className="px-5 py-3 text-right">{overdue(o) && <Badge status="overdue" />}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
