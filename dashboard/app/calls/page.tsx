import type { Metadata } from "next";
import AudioPlayer from "@/components/AudioPlayer";
import { Card, Empty, PageTitle } from "@/components/ui";
import { signAudio } from "@/lib/audio";
import { fmtSecs, fmtTime } from "@/lib/format";
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

  return (
    <>
      <PageTitle sub={`Latest ${LIMIT} voice notes and calls`}>Calls</PageTitle>
      {calls.length === 0 ? (
        <Card>
          <Empty>No calls yet. Send a voice note to the Recall WhatsApp number.</Empty>
        </Card>
      ) : (
        <ul className="space-y-3">
          {calls.map((c) => (
            <li key={c.id} id={`call-${c.id}`} className="scroll-mt-20">
              <Card className="p-4 target:ring-2">
                <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                  <span className="font-medium">{c.clients?.name ?? (c.from_phone ? `+${c.from_phone}` : "Unknown sender")}</span>
                  <span className="text-xs text-muted">
                    #{c.id} · {fmtTime(c.created_at)}
                    {c.duration_seconds != null && ` · ${fmtSecs(c.duration_seconds)}`}
                  </span>
                </div>
                <div className="mt-3">
                  <AudioPlayer src={c.audio_url ? signed.get(c.audio_url) ?? null : null} />
                </div>
                {c.transcript ? (
                  <p className="mt-3 whitespace-pre-wrap rounded-lg bg-line/40 p-3 text-sm leading-relaxed">{c.transcript}</p>
                ) : (
                  <p className="mt-3 text-sm italic text-muted">Transcribing…</p>
                )}
              </Card>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
