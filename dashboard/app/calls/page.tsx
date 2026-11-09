import type { Metadata } from "next";
import AudioPlayer from "@/components/AudioPlayer";
import { Card, Empty, PageTitle } from "@/components/ui";
import { signAudio } from "@/lib/audio";
import { fmtTime } from "@/lib/format";
import { Highlight } from "@/lib/highlight";
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
      <PageTitle sub="Every voice note, with what Recall heard. Quantities and rates are marked in colour, items are underlined.">
        Calls
      </PageTitle>
      {calls.length === 0 ? (
        <Card>
          <Empty>No calls yet. Send a voice note to the Recall WhatsApp number.</Empty>
        </Card>
      ) : (
        <ul className="space-y-4">
          {calls.map((c) => (
            <li key={`${c.id}-${c.transcript ? "t" : "p"}`} id={`call-${c.id}`} className="fresh scroll-mt-24">
              <Card className="overflow-hidden transition-colors duration-300 [:target>&]:border-accent/70">
                <div className="grid gap-4 p-4 sm:p-5 md:grid-cols-[220px_1fr] md:gap-8">
                  <div className="min-w-0 space-y-3">
                    <div>
                      <p className="truncate font-semibold">
                        {c.clients?.name ?? (c.from_phone ? `+${c.from_phone}` : "Unknown sender")}
                      </p>
                      <p className="text-sm text-muted">
                        {fmtTime(c.created_at)}, call #{c.id}
                      </p>
                    </div>
                    <AudioPlayer
                      src={c.audio_url ? (signed.get(c.audio_url) ?? null) : null}
                      duration={c.duration_seconds}
                    />
                  </div>
                  {c.transcript ? (
                    <p lang="hi" className="max-w-[68ch] text-[17px] whitespace-pre-wrap text-ink/90">
                      <Highlight text={c.transcript} />
                    </p>
                  ) : (
                    <p className="text-[15px] text-muted">Transcribing…</p>
                  )}
                </div>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
