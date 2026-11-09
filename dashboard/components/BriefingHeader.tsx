"use client";

import { useState, useTransition } from "react";
import { previewBriefing, type BriefingPreview } from "@/app/actions";
import AudioPlayer from "@/components/AudioPlayer";
import { PageHeader } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

/** Home page header with a "Morning briefing" button: builds today's briefing and plays it, without sending it. */
export default function BriefingHeader({ date }: { date: string }) {
  const [busy, startTransition] = useTransition();
  const [briefing, setBriefing] = useState<BriefingPreview | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setError(null);
    startTransition(async () => {
      const res = await previewBriefing();
      if (res.ok) setBriefing(res.data);
      else setError(`Couldn't build the briefing: ${res.error}`);
    });
  };

  return (
    <>
      <PageHeader
        title="Orders"
        aside={
          <div className="flex items-center gap-4">
            <span>{date}</span>
            <Button variant="outline" size="sm" onClick={load} disabled={busy}>
              {busy ? "Preparing…" : "Morning briefing"}
            </Button>
          </div>
        }
      />
      {error && <p className="-mt-3 mb-6 text-[13px] text-muted-foreground">{error}</p>}
      {briefing && (
        <Card className="mb-6 gap-3 px-4">
          <div className="flex items-baseline justify-between gap-4">
            <h2 className="font-medium">Morning briefing</h2>
            <Button variant="ghost" size="xs" className="text-muted-foreground" onClick={() => setBriefing(null)}>
              Close
            </Button>
          </div>
          {briefing.audio && <AudioPlayer key={briefing.audio} src={briefing.audio} autoPlay />}
          {briefing.error && <p className="text-[13px] text-muted-foreground">No audio: {briefing.error}</p>}
          <p lang="hi" className="max-w-prose whitespace-pre-wrap text-muted-foreground">
            {briefing.text || "Nothing to report today."}
          </p>
        </Card>
      )}
    </>
  );
}
