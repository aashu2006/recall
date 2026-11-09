import type { Metadata } from "next";
import AudioPlayer from "@/components/AudioPlayer";
import { Empty, PageHeader } from "@/components/common";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { signAudio } from "@/lib/audio";
import { fmtTime } from "@/lib/format";
import { db, must } from "@/lib/supabase";
import type { Client, WaSend } from "@/lib/types";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Outbox" };

const LIMIT = 100;

const KIND_LABEL: Record<string, string> = {
  client_summary: "Order summary",
  owner_question: "Question",
  owner_reply: "Reply",
  owner_alert: "Alert",
  briefing: "Briefing",
  // Rows from before 004 hold the message type.
  text: "Text",
  buttons: "Question",
  audio: "Voice note",
};

/** Last 10 digits, so "+91 98xxx" and "9198xxx" match. */
const phoneKey = (p: string | null | undefined) => (p ?? "").replace(/\D/g, "").slice(-10);

export default async function OutboxPage() {
  const [sendsRes, clientsRes] = await Promise.all([
    db().from("wa_sends").select("*").order("created_at", { ascending: false }).order("id", { ascending: false }).limit(LIMIT),
    db().from("clients").select("id, name, phone"),
  ]);
  const sends = must<WaSend[]>(sendsRes);
  const clients = must<Client[]>(clientsRes);
  const byPhone = new Map(clients.filter((c) => phoneKey(c.phone)).map((c) => [phoneKey(c.phone), c.name]));
  const signed = await signAudio(sends.map((s) => s.media_path));

  // Order summaries go to clients; questions, replies, alerts and briefings go to the owner.
  const recipient = (s: WaSend) =>
    s.kind.startsWith("owner_") || s.kind === "briefing" ? "Owner" : (byPhone.get(phoneKey(s.to_phone)) ?? "Owner");

  return (
    <>
      <PageHeader
        title="Outbox"
        description="Every WhatsApp message Recall sent or tried to send."
        aside={sends.length > 0 && `${sends.length} ${sends.length === 1 ? "message" : "messages"}`}
      />
      <Card className="gap-0 py-0">
        {sends.length === 0 ? (
          <Empty>Nothing sent yet.</Empty>
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className="w-36 pl-4 text-muted-foreground">Time</TableHead>
                <TableHead className="w-48 text-muted-foreground">To</TableHead>
                <TableHead className="w-28 text-muted-foreground">Kind</TableHead>
                <TableHead className="text-muted-foreground">Message</TableHead>
                <TableHead className="w-24 pr-4 text-muted-foreground">Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sends.map((s) => {
                const audio = s.media_path ? (signed.get(s.media_path) ?? null) : null;
                const status = s.status ?? "sent"; // before 004 only successful sends were logged
                return (
                  <TableRow key={s.id} className="hover:bg-transparent">
                    <TableCell className="pl-4 align-top text-muted-foreground tabular-nums">{fmtTime(s.created_at)}</TableCell>
                    <TableCell className="align-top font-medium">{recipient(s)}</TableCell>
                    <TableCell className="align-top">{KIND_LABEL[s.kind] ?? s.kind}</TableCell>
                    <TableCell className="align-top whitespace-normal">
                      {s.body ? (
                        <p lang="hi" className="max-w-prose whitespace-pre-wrap">
                          {s.body}
                        </p>
                      ) : (
                        !s.media_path && <span className="text-muted-foreground">—</span>
                      )}
                      {s.media_path && (
                        <div className={s.body ? "mt-2" : ""}>
                          <AudioPlayer src={audio} />
                        </div>
                      )}
                      {s.error && <p className="mt-1 text-[13px] text-muted-foreground">{s.error}</p>}
                    </TableCell>
                    <TableCell className="pr-4 align-top">
                      <Badge variant="outline">{status[0].toUpperCase() + status.slice(1)}</Badge>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </Card>
    </>
  );
}
