"use client";

import { ChevronRight } from "lucide-react";
import { Fragment, useEffect, useState } from "react";
import AudioPlayer from "@/components/AudioPlayer";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { fmtSecs, fmtTime } from "@/lib/format";
import { Highlight } from "@/lib/highlight";
import { cn } from "@/lib/utils";
import type { Call } from "@/lib/types";

type Row = Call & { audio: string | null };

/** One row per call; clicking a row shows its recording and transcript. /calls#call-12 opens call 12. */
export default function CallsTable({ calls }: { calls: Row[] }) {
  const [open, setOpen] = useState<Set<number>>(new Set());

  useEffect(() => {
    const m = window.location.hash.match(/^#call-(\d+)$/);
    if (!m) return;
    const id = Number(m[1]);
    setOpen((s) => new Set(s).add(id));
    requestAnimationFrame(() => document.getElementById(`call-${id}`)?.scrollIntoView({ block: "start" }));
  }, []);

  const toggle = (id: number) =>
    setOpen((s) => {
      const next = new Set(s);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead className="w-10 pl-4" />
          <TableHead className="text-muted-foreground">Time</TableHead>
          <TableHead className="text-muted-foreground">Client</TableHead>
          <TableHead className="pr-4 text-right text-muted-foreground">Duration</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {calls.map((c) => {
          const expanded = open.has(c.id);
          return (
            <Fragment key={c.id}>
              <TableRow
                id={`call-${c.id}`}
                className={cn("scroll-mt-16 cursor-pointer", expanded && "border-b-0 bg-muted/50")}
                onClick={() => toggle(c.id)}
              >
                <TableCell className="pl-4">
                  <button
                    type="button"
                    aria-expanded={expanded}
                    aria-label={expanded ? "Hide transcript" : "Show transcript"}
                    className="grid size-5 place-items-center rounded text-muted-foreground"
                    onClick={(ev) => {
                      ev.stopPropagation();
                      toggle(c.id);
                    }}
                  >
                    <ChevronRight className={cn("size-4 transition-transform", expanded && "rotate-90")} />
                  </button>
                </TableCell>
                <TableCell className="w-40 text-muted-foreground tabular-nums">{fmtTime(c.created_at)}</TableCell>
                <TableCell className="font-medium">
                  {c.clients?.name ?? (c.from_phone ? `+${c.from_phone}` : "Unknown sender")}
                </TableCell>
                <TableCell className="num w-24 pr-4 text-right">{fmtSecs(c.duration_seconds)}</TableCell>
              </TableRow>
              {expanded && (
                <TableRow className="bg-muted/50 hover:bg-muted/50">
                  <TableCell colSpan={4} className="px-4 pt-1 pb-4 pl-14 whitespace-normal">
                    <AudioPlayer src={c.audio} duration={c.duration_seconds} />
                    <p lang="hi" className="mt-3 max-w-prose whitespace-pre-wrap text-muted-foreground">
                      {c.transcript == null ? (
                        "Transcribing…"
                      ) : c.transcript.trim() === "" ? (
                        "No speech found."
                      ) : (
                        <Highlight text={c.transcript} />
                      )}
                    </p>
                  </TableCell>
                </TableRow>
              )}
            </Fragment>
          );
        })}
      </TableBody>
    </Table>
  );
}
