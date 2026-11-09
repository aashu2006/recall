"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { resolvePending } from "@/app/actions";
import { Button } from "@/components/ui/button";

/** Same choices as the owner's WhatsApp buttons. Each one resolves through the backend. */
export default function PendingOptions({ id, options }: { id: number; options: string[] }) {
  const router = useRouter();
  const [busy, startTransition] = useTransition();
  const [choice, setChoice] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  const answer = (c: string) => {
    setChoice(c);
    setNote(null);
    startTransition(async () => {
      const res = await resolvePending(id, c);
      // Backend replies are written for WhatsApp; drop the leading emoji.
      if (!res.ok) setNote(`Couldn't send the answer: ${res.error}`);
      else if (res.data) setNote(res.data.replace(/^[\p{Extended_Pictographic}️\s]+/u, ""));
      router.refresh();
    });
  };

  const label = (c: string) => (c === "new" ? "Naya order" : c === "no" ? "Nahi" : `Order #${c}`);

  return (
    <div className="mt-3">
      <div className="flex flex-wrap items-center gap-2">
        {[...options, "no"].map((c) => (
          <Button key={c} variant="outline" size="sm" disabled={busy} onClick={() => answer(c)}>
            <span className="num">{busy && choice === c ? "Sending…" : label(c)}</span>
          </Button>
        ))}
      </div>
      {note && <p className="mt-2 text-[13px] text-muted-foreground">{note}</p>}
    </div>
  );
}
