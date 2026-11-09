"use client";

import { useEffect, useRef, useState } from "react";
import { fmtSecs } from "@/lib/format";

interface Props {
  src: string | null;
  /** Clip bounds in seconds. When set, playback starts at start and stops at end. */
  start?: number | null;
  end?: number | null;
  /** Total length, if known, so a full recording shows its length before it loads. */
  duration?: number | null;
  /** "proof": the large player on an order's change history. "compact": a call in the list. */
  variant?: "proof" | "compact";
  /** Button text when idle. */
  label?: string;
}

/**
 * A play button with a progress line over a real <audio> element (AutoRefresh checks for playing
 * <audio> to pause refreshes).
 *
 * Signed URLs change on every server refresh, so the first src is kept and only swapped
 * for the latest one if loading fails (e.g. the signature expired). This keeps the
 * 10 s auto refresh from restarting playback.
 */
export default function AudioPlayer({ src, start, end, duration, variant = "compact", label: idleLabel }: Props) {
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

  if (!current)
    return (
      <p className="flex items-center gap-2 text-sm text-soft">
        <span className="grid h-7 w-7 place-items-center rounded-full border border-dashed border-ink/25" aria-hidden>
          <PlayIcon />
        </span>
        Recording not available
      </p>
    );

  const clip = start != null && end != null && Number(end) > Number(start);
  const lo = clip ? Number(start) : 0;
  const hi = clip ? Number(end) : total;
  const url = clip ? `${current}#t=${lo},${hi}` : current;
  const progress = time != null && hi ? Math.min(1, Math.max(0, (time - lo) / (hi - lo))) : 0;

  const toggle = () => {
    const a = ref.current;
    if (!a) return;
    if (a.paused) void a.play().catch(() => setPlaying(false));
    else a.pause();
  };

  const length = clip ? hi! - lo : hi;
  const elapsed = time != null ? Math.max(0, time - lo) : 0;
  const big = variant === "proof";
  const title = playing ? "Playing" : (idleLabel ?? (clip ? "Play the proof" : "Play recording"));
  const where = clip ? `${fmtSecs(lo)}–${fmtSecs(hi)} of the call` : null;

  return (
    <div className={`flex items-center ${big ? "gap-4" : "gap-3"} w-full`}>
      <button
        type="button"
        onClick={toggle}
        aria-label={playing ? "Pause recording" : clip ? "Play the part where this was said" : "Play recording"}
        className={`grid shrink-0 place-items-center rounded-full bg-ink text-paper transition-transform duration-150 hover:scale-[1.04] active:scale-95 ${
          big ? "h-12 w-12" : "h-9 w-9"
        } ${playing ? "ring-4 ring-ink/12" : ""}`}
      >
        {playing ? <PauseIcon big={big} /> : <PlayIcon big={big} />}
      </button>
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-3">
          <span className={`truncate font-medium ${big ? "text-[15px]" : "text-sm"}`}>{title}</span>
          <span className="num shrink-0 text-[13px] text-soft">
            {playing || time != null ? `${fmtSecs(elapsed)} / ` : ""}
            {fmtSecs(length)}
          </span>
        </div>
        <div className={`relative mt-2 overflow-hidden rounded-full bg-ink/12 ${big ? "h-1.5" : "h-1"}`} aria-hidden>
          <span
            className="absolute inset-y-0 left-0 rounded-full bg-ink transition-[width] duration-200 ease-linear"
            style={{ width: `${progress * 100}%` }}
          />
        </div>
        {big && where && <p className="num mt-1.5 text-[12px] text-faint">{where}</p>}
      </div>
      <audio
        ref={ref}
        preload={clip || duration != null ? "none" : "metadata"}
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

function PlayIcon({ big = false }: { big?: boolean }) {
  return (
    <svg viewBox="0 0 20 20" className={`ml-0.5 ${big ? "h-5 w-5" : "h-3.5 w-3.5"}`} fill="currentColor" aria-hidden>
      <path d="M6 4.2v11.6a.8.8 0 0 0 1.2.7l9.3-5.8a.8.8 0 0 0 0-1.4L7.2 3.5A.8.8 0 0 0 6 4.2Z" />
    </svg>
  );
}

function PauseIcon({ big = false }: { big?: boolean }) {
  return (
    <svg viewBox="0 0 20 20" className={big ? "h-5 w-5" : "h-3.5 w-3.5"} fill="currentColor" aria-hidden>
      <rect x="5" y="4" width="3.5" height="12" rx="1" />
      <rect x="11.5" y="4" width="3.5" height="12" rx="1" />
    </svg>
  );
}
