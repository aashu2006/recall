// All times shown in IST; the factory and its clients are in India.
export const TZ = "Asia/Kolkata";

/** YYYY-MM-DD for today + offsetDays, in IST. */
export function istDate(offsetDays = 0): string {
  const d = new Date(Date.now() + offsetDays * 86_400_000);
  return new Intl.DateTimeFormat("en-CA", { timeZone: TZ }).format(d);
}

/** "Mon, 9 Nov" (or "Monday, 9 November" when long) from a YYYY-MM-DD date column. */
export function fmtDate(date: string | null, long = false): string {
  if (!date) return "—";
  const d = new Date(`${date}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return date;
  const style = long ? "long" : "short";
  return d.toLocaleDateString("en-IN", { timeZone: "UTC", weekday: style, day: "numeric", month: style });
}

/** "9 Nov, 4:05 pm" from a timestamptz. */
export function fmtTime(ts: string): string {
  return new Date(ts).toLocaleString("en-IN", {
    timeZone: TZ,
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });
}

export function fmtNum(n: number | string | null | undefined): string {
  if (n === null || n === undefined || n === "") return "—";
  const v = Number(n);
  return Number.isFinite(v) ? v.toLocaleString("en-IN", { maximumFractionDigits: 3 }) : String(n);
}

export function fmtRate(n: number | string | null | undefined, unit?: string | null): string {
  if (n === null || n === undefined || n === "") return "—";
  return `₹${fmtNum(n)}${unit ? `/${unit}` : ""}`;
}

/** "0:42" from seconds. */
export function fmtSecs(s: number | null | undefined): string {
  if (s === null || s === undefined) return "—";
  const t = Math.max(0, Math.round(Number(s)));
  return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, "0")}`;
}

const FIELD_LABELS: Record<string, string> = {
  created: "Order created",
  item: "Item",
  spec: "Spec",
  quantity: "Quantity",
  unit: "Unit",
  rate: "Rate",
  delivery_date: "Delivery date",
  status: "Status",
  client_id: "Client",
};

export function fieldLabel(field: string): string {
  return FIELD_LABELS[field] ?? field.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
}

/** Format an order_changes value according to its field. */
export function fmtChangeValue(field: string, value: string | null): string {
  if (value === null || value === "") return "—";
  if (field === "delivery_date" && /^\d{4}-\d{2}-\d{2}$/.test(value)) return fmtDate(value);
  if (field === "rate") return fmtRate(value);
  if (field === "quantity") return fmtNum(value);
  return value;
}

/** "+100", "−₹3" for numeric quantity/rate changes, else null. */
export function fmtDelta(field: string, oldValue: string | null, newValue: string | null): string | null {
  if (field !== "quantity" && field !== "rate") return null;
  const a = Number(oldValue);
  const b = Number(newValue);
  if (oldValue == null || newValue == null || !Number.isFinite(a) || !Number.isFinite(b) || a === b) return null;
  const d = Math.abs(b - a);
  return `${b > a ? "+" : "−"}${field === "rate" ? "₹" : ""}${fmtNum(d)}`;
}

/** Where a change came from when it has no call: seeded or typed in by the owner. */
export function manualLabel(field: string): string {
  return field === "created" ? "Added manually" : "Edited manually";
}
