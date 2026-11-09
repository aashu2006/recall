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
      <PageTitle
        sub={
          <>
            Every voice note, written down as Recall heard it. Quantities and rates are in{" "}
            <mark className="bg-transparent font-semibold text-ink">bold</mark>, items are{" "}
            <mark className="bg-transparent text-ink underline decoration-red/60 decoration-[1.5px] underline-offset-[5px]">underlined</mark>.
          </>
        }
        aside={calls.length > 0 && <span className="num text-sm text-soft">{calls.length} {calls.length === 1 ? "voice note" : "voice notes"}</span>}
      >
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
                className="fresh scroll-mt-28 transition-colors duration-500 target:bg-paper-2/70"
              >
                <div className="grid gap-x-10 gap-y-4 px-4 py-6 sm:px-6 md:grid-cols-[250px_1fr]">
                  <div className="min-w-0">
                    <p className="truncate text-[17px] font-medium">
                      {c.clients?.name ?? (c.from_phone ? `+${c.from_phone}` : "Unknown sender")}
                    </p>
                    <p className="num mt-0.5 text-sm text-soft">
                      {fmtTime(c.created_at)}
                      <span className="mx-1.5 text-rule">|</span>
                      <span className="text-faint">Call #{c.id}</span>
                    </p>
                    <div className="mt-4 max-w-[320px]">
                      <AudioPlayer src={c.audio_url ? (signed.get(c.audio_url) ?? null) : null} duration={c.duration_seconds} />
                    </div>
                  </div>
                  {c.transcript == null ? (
                    <p className="flex items-center gap-2 text-[15px] text-soft">
                      <span className="h-2 w-2 rounded-full bg-ink/40 motion-safe:animate-pulse" aria-hidden />
                      Transcribing…
                    </p>
                  ) : c.transcript.trim() === "" ? (
                    <p className="text-[15px] text-soft">No speech found</p>
                  ) : (
                    <p lang="hi" className="ruled max-w-[66ch] text-[17px] whitespace-pre-wrap text-ink/85">
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
