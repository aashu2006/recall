import { Mic } from "lucide-react";
import Link from "next/link";
import BriefingHeader from "@/components/BriefingHeader";
import { Empty, StatCard, Unit } from "@/components/common";
import FlashBody from "@/components/FlashBody";
import { Card } from "@/components/ui/card";
import { Table, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { fmtAgo, fmtDate, fmtNum, fmtRate, istDate } from "@/lib/format";
import { db, must } from "@/lib/supabase";
import type { Order } from "@/lib/types";

export const dynamic = "force-dynamic";

/** Orders changed this recently get a blue edge and an "Updated" note. */
const RECENT_MS = 10 * 60_000;
const ACTIVITY_LIMIT = 5;

interface ChangeRow {
  id: number;
  order_id: number;
  call_id: number | null;
  field: string;
  created_at: string;
  orders: { clients: { name: string } | null } | null;
}

interface Activity {
  key: string;
  orderId: number;
  callId: number | null;
  client: string;
  created: boolean;
  count: number;
  at: string;
}

async function load() {
  const [orders, pending, changes] = await Promise.all([
    db()
      .from("orders")
      .select("*, clients(name)")
      .eq("status", "open")
      .order("delivery_date", { ascending: true, nullsFirst: false })
      .order("created_at", { ascending: true })
      .limit(500),
    db().from("pending_confirmations").select("id", { count: "exact", head: true }).eq("status", "pending"),
    db()
      .from("order_changes")
      .select("id, order_id, call_id, field, created_at, orders(clients(name))")
      .order("created_at", { ascending: false })
      .order("id", { ascending: false })
      .limit(50),
  ]);
  if (pending.error) throw new Error(pending.error.message);
  const open = must<Order[]>(orders);

  // Orders whose "created" history row came from a call: shown with a mic icon.
  const ids = open.map((o) => o.id);
  const fromCall = ids.length
    ? must<{ order_id: number }[]>(
        await db().from("order_changes").select("order_id").eq("field", "created").not("call_id", "is", null).in("order_id", ids),
      )
    : [];

  return {
    orders: open,
    pendingCount: pending.count ?? 0,
    activity: groupActivity(must<ChangeRow[]>(changes)),
    voiceOrders: new Set(fromCall.map((r) => r.order_id)),
  };
}

/** One entry per (order, call, moment): a voice note that changed qty and rate is one entry, "2 changes". */
function groupActivity(rows: ChangeRow[]): Activity[] {
  const out = new Map<string, Activity>();
  for (const r of rows) {
    const key = [r.order_id, r.call_id ?? "manual", r.created_at.slice(0, 19)].join("|");
    let a = out.get(key);
    if (!a) {
      if (out.size === ACTIVITY_LIMIT) break;
      a = {
        key,
        orderId: r.order_id,
        callId: r.call_id,
        client: r.orders?.clients?.name ?? "Unknown client",
        created: false,
        count: 0,
        at: r.created_at,
      };
      out.set(key, a);
    }
    if (r.field === "created") a.created = true;
    else a.count++;
  }
  return [...out.values()];
}

export default async function Home() {
  const { orders, pendingCount, activity, voiceOrders } = await load();
  const now = Date.now();
  const today = istDate(0);
  const tomorrow = istDate(1);
  const isOverdue = (o: Order) => !!o.delivery_date && o.delivery_date < today;
  const isRecent = (o: Order) => now - new Date(o.updated_at).getTime() < RECENT_MS;
  const dueToday = orders.filter((o) => o.delivery_date === today).length;
  const overdue = orders.filter(isOverdue).length;
  const dueLabel = (d: string | null) => (d === today ? "Today" : d === tomorrow ? "Tomorrow" : fmtDate(d));

  return (
    <>
      <BriefingHeader date={fmtDate(today, true)} />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard label="Open orders" value={orders.length} />
        <StatCard label="Due today" value={dueToday} />
        <StatCard label="Overdue" value={overdue} alert={overdue > 0} />
        <StatCard label="Needs confirmation" value={pendingCount} href="/pending" />
      </div>

      <h2 className="mt-8 mb-3 font-medium">Recent activity</h2>
      <Card className="gap-0 py-0">
        {activity.length === 0 ? (
          <Empty>No activity yet.</Empty>
        ) : (
          <ul className="divide-y">
            {activity.map((a) => (
              <li key={a.key}>
                <Link href={`/orders/${a.orderId}`} className="flex items-baseline justify-between gap-4 px-4 py-2.5 transition-colors hover:bg-muted/50">
                  <span className="min-w-0 truncate">
                    <span className="font-medium">{a.client}</span>
                    <span className="text-muted-foreground">
                      {" · "}
                      {a.callId != null ? "voice note" : "manual"}
                      {" · "}
                      {a.created ? "new order" : `${a.count} ${a.count === 1 ? "change" : "changes"}`}
                      {" · "}
                      <span className="num">#{a.orderId}</span>
                    </span>
                  </span>
                  <span className="num shrink-0 text-[13px] text-muted-foreground">{fmtAgo(a.at, now)}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <h2 className="mt-8 mb-3 font-medium">Open orders</h2>
      <Card className="gap-0 py-0">
        {orders.length === 0 ? (
          <Empty>No open orders yet.</Empty>
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className="w-20 pl-4 text-muted-foreground">Order</TableHead>
                <TableHead className="text-muted-foreground">Client</TableHead>
                <TableHead className="text-muted-foreground">Item</TableHead>
                <TableHead className="text-right text-muted-foreground">Qty</TableHead>
                <TableHead className="text-right text-muted-foreground">Rate</TableHead>
                <TableHead className="w-44 pr-4 text-muted-foreground">Due</TableHead>
              </TableRow>
            </TableHeader>
            <FlashBody>
              {orders.map((o) => {
                const recent = isRecent(o);
                return (
                  <TableRow key={o.id} data-flash-id={o.id} data-flash-version={o.updated_at} className="relative">
                    <TableCell className={`num pl-4 text-muted-foreground ${recent ? "shadow-[inset_2px_0_0_var(--primary)]" : ""}`}>
                      <span className="inline-flex items-center gap-1.5">
                        #{o.id}
                        {voiceOrders.has(o.id) && <Mic aria-label="From a voice note" className="size-3.5" />}
                      </span>
                    </TableCell>
                    <TableCell className="font-medium">
                      {/* Stretched link: the whole row opens the order. */}
                      <Link href={`/orders/${o.id}`} className="outline-none after:absolute after:inset-0 focus-visible:underline">
                        {o.clients?.name ?? "Unknown client"}
                      </Link>
                    </TableCell>
                    <TableCell>
                      {o.item}
                      {o.spec && <span className="ml-1.5 text-muted-foreground">{o.spec}</span>}
                    </TableCell>
                    <TableCell className="text-right">
                      <span className="num">{fmtNum(o.quantity)}</span>
                      <Unit>{o.unit}</Unit>
                    </TableCell>
                    <TableCell className="num text-right">{fmtRate(o.rate)}</TableCell>
                    <TableCell className="pr-4">
                      <span className={isOverdue(o) ? "text-destructive" : ""}>{dueLabel(o.delivery_date)}</span>
                      {recent && <span className="ml-2 text-xs text-muted-foreground">Updated</span>}
                    </TableCell>
                  </TableRow>
                );
              })}
            </FlashBody>
          </Table>
        )}
      </Card>
    </>
  );
}
