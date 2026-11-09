import Link from "next/link";
import { Empty, PageHeader, StatCard, Unit } from "@/components/common";
import { Card } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
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
  const isOverdue = (o: Order) => !!o.delivery_date && o.delivery_date < today;
  const dueToday = orders.filter((o) => o.delivery_date === today).length;
  const overdue = orders.filter(isOverdue).length;
  const dueLabel = (d: string | null) => (d === today ? "Today" : d === tomorrow ? "Tomorrow" : fmtDate(d));

  return (
    <>
      <PageHeader title="Orders" aside={fmtDate(today, true)} />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard label="Open orders" value={orders.length} />
        <StatCard label="Due today" value={dueToday} />
        <StatCard label="Overdue" value={overdue} alert={overdue > 0} />
        <StatCard label="Needs confirmation" value={pendingCount} href="/pending" />
      </div>

      <Card className="mt-6 gap-0 py-0">
        {orders.length === 0 ? (
          <Empty>No open orders yet.</Empty>
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className="w-16 pl-4 text-muted-foreground">Order</TableHead>
                <TableHead className="text-muted-foreground">Client</TableHead>
                <TableHead className="text-muted-foreground">Item</TableHead>
                <TableHead className="text-right text-muted-foreground">Qty</TableHead>
                <TableHead className="text-right text-muted-foreground">Rate</TableHead>
                <TableHead className="w-32 pr-4 text-muted-foreground">Due</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {orders.map((o) => (
                <TableRow key={o.id} className="relative">
                  <TableCell className="num pl-4 text-muted-foreground">#{o.id}</TableCell>
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
                  <TableCell className={`pr-4 ${isOverdue(o) ? "text-destructive" : ""}`}>{dueLabel(o.delivery_date)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>
    </>
  );
}
