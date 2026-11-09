"use client";

import { Pause, Play } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { fmtSecs } from "@/lib/format";

interface Props {
  src: string | null;
  /** Clip bounds in seconds. When set, playback starts at start and stops at end. */
  start?: number | null;
  end?: number | null;
  /** Total length, if known, so a full recording shows its length before it loads. */
  duration?: number | null;
  /** Start playing as soon as it mounts (right after the user asked for it). */
  autoPlay?: boolean;
}

/**
 * A small inline player: play button, progress line, time. Wraps a real <audio> element
 * (AutoRefresh checks for playing <audio> to pause refreshes).
 *
 * Signed URLs change on every server refresh, so the first src is kept and only swapped
 * for the latest one if loading fails (e.g. the signature expired). This keeps the
 * 10 s auto refresh from restarting playback.
 */
export default function AudioPlayer({ src, start, end, duration, autoPlay = false }: Props) {
  const [current, setCurrent] = useState(src);
  const latest = useRef(src);
  const ref = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  const [time, setTime] = useState<number | null>(null);
  const [total, setTotal] = useState<number | null>(duration ?? null);

  useEffect(() => {
    latest.current = src;
    if (!current && src) setCurrent(src);
  }, [src, current]);

  useEffect(() => {
    // Browsers may block this if the click was too long ago; the play button still works.
    if (autoPlay) void ref.current?.play().catch(() => setPlaying(false));
  }, [autoPlay]);

  if (!current) return <p className="text-[13px] text-muted-foreground">Recording not available</p>;

  const clip = start != null && end != null && Number(end) > Number(start);
  const lo = clip ? Number(start) : 0;
  const hi = clip ? Number(end) : total;
  const url = clip ? `${current}#t=${lo},${hi}` : current;
  const progress = time != null && hi ? Math.min(1, Math.max(0, (time - lo) / (hi - lo))) : 0;
  const length = clip ? hi! - lo : hi;
  const elapsed = time != null ? Math.max(0, time - lo) : 0;

  const toggle = () => {
    const a = ref.current;
    if (!a) return;
    if (a.paused) void a.play().catch(() => setPlaying(false));
    else a.pause();
  };

  return (
    <div className="flex w-full max-w-xs items-center gap-3">
      <Button
        type="button"
        variant="outline"
        size="icon-sm"
        onClick={toggle}
        aria-label={playing ? "Pause" : clip ? "Play the part where this was said" : "Play recording"}
      >
        {playing ? <Pause className="fill-current" /> : <Play className="fill-current" />}
      </Button>
      <div className="h-1 flex-1 overflow-hidden rounded-full bg-muted" aria-hidden>
        <div className="h-full rounded-full bg-primary" style={{ width: `${progress * 100}%` }} />
      </div>
      <span className="num shrink-0 text-xs text-muted-foreground">
        {playing || time != null ? `${fmtSecs(elapsed)} / ` : ""}
        {fmtSecs(length)}
      </span>
      <audio
        ref={ref}
        preload={autoPlay ? "auto" : clip || duration != null ? "none" : "metadata"}
        src={url}
        className="hidden"
        onError={() => {
          if (latest.current && latest.current !== current) setCurrent(latest.current);
        }}
        onLoadedMetadata={() => {
          const d = ref.current?.duration;
          if (d && Number.isFinite(d)) setTotal(d);
        }}
        onPlay={() => {
          const a = ref.current;
          if (a && clip && (a.currentTime < lo || a.currentTime >= hi!)) a.currentTime = lo;
          setPlaying(true);
        }}
        onPause={() => setPlaying(false)}
        onEnded={() => {
          setPlaying(false);
          setTime(null);
        }}
        onTimeUpdate={() => {
          const a = ref.current;
          if (!a) return;
          if (clip && a.currentTime >= hi!) {
            a.pause();
            a.currentTime = lo;
            setTime(null);
            return;
          }
          setTime(a.currentTime);
        }}
      />
    </div>
  );
}
