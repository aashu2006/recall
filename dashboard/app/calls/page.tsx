import type { Metadata } from "next";
import CallsTable from "@/app/calls/CallsTable";
import { Empty, PageHeader } from "@/components/common";
import { Card } from "@/components/ui/card";
import { signAudio } from "@/lib/audio";
import { db, must } from "@/lib/supabase";
import type { Call } from "@/lib/types";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Calls" };

const LIMIT = 50;

export default async function CallsPage() {
  const calls = must<Call[]>(
    await db()
      .from("calls")
      .select("id, client_id, from_phone, audio_url, duration_seconds, transcript, created_at, clients(name)")
      .order("created_at", { ascending: false })
      .limit(LIMIT),
  );
  const signed = await signAudio(calls.map((c) => c.audio_url));
  const rows = calls.map((c) => ({ ...c, audio: c.audio_url ? (signed.get(c.audio_url) ?? null) : null }));

  return (
    <>
      <PageHeader
        title="Calls"
        description="Every voice note and its transcript."
        aside={calls.length > 0 && `${calls.length} ${calls.length === 1 ? "call" : "calls"}`}
      />
      <Card className="gap-0 py-0">
        {rows.length === 0 ? <Empty>No calls yet. Send a voice note to the Recall WhatsApp number.</Empty> : <CallsTable calls={rows} />}
      </Card>
    </>
  );
}
