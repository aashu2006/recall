import type { Metadata } from "next";
import AudioPlayer from "@/components/AudioPlayer";
import { Empty, PageTitle, Register } from "@/components/ui";
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
      <PageTitle sub="Every voice note, written down as Recall heard it. Quantities and rates are in bold, items are underlined.">
        Calls
      </PageTitle>
      <Register>
        {calls.length === 0 ? (
          <Empty>No calls yet. Send a voice note to the Recall WhatsApp number.</Empty>
        ) : (
          <ul className="divide-y divide-rule">
            {calls.map((c) => (
              <li
                key={`${c.id}-${c.transcript == null ? "p" : "t"}`}
                id={`call-${c.id}`}
                className="fresh scroll-mt-28 transition-colors duration-500 target:bg-paper-2"
              >
                <div className="grid gap-x-8 gap-y-3 px-4 py-5 sm:px-5 md:grid-cols-[230px_1fr]">
                  <div className="min-w-0 space-y-2.5">
                    <div>
                      <p className="truncate text-[16px] font-medium">
                        {c.clients?.name ?? (c.from_phone ? `+${c.from_phone}` : "Unknown sender")}
                      </p>
                      <p className="text-sm text-soft">
                        <span className="num">{fmtTime(c.created_at)}</span>, call <span className="num">#{c.id}</span>
                      </p>
                    </div>
                    <AudioPlayer src={c.audio_url ? (signed.get(c.audio_url) ?? null) : null} duration={c.duration_seconds} />
                  </div>
                  {c.transcript == null ? (
                    <p className="text-[15px] text-soft">Transcribing…</p>
                  ) : c.transcript.trim() === "" ? (
                    <p className="text-[15px] text-soft">No speech found</p>
                  ) : (
                    <p lang="hi" className="ruled max-w-[68ch] text-[17px] whitespace-pre-wrap text-ink/80">
                      <Highlight text={c.transcript} />
                    </p>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Register>
    </>
  );
}
