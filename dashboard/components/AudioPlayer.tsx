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
}

/**
 * A small "Play recording" pill over a real <audio> element (AutoRefresh checks for playing
 * <audio> to pause refreshes). The pill fills from left to right as it plays.
 *
 * Signed URLs change on every server refresh, so the first src is kept and only swapped
 * for the latest one if loading fails (e.g. the signature expired). This keeps the
 * 10 s auto refresh from restarting playback.
 */
export default function AudioPlayer({ src, start, end, duration }: Props) {
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

  if (!current) return <p className="text-sm text-soft">Recording not available</p>;

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

  const span = clip ? `${fmtSecs(lo)}–${fmtSecs(hi)}` : hi ? fmtSecs(hi) : "";
  const label = playing || time != null ? `${fmtSecs(time ?? lo)} / ${clip ? fmtSecs(hi) : span}` : span;

  return (
    <>
      <button
        type="button"
        onClick={toggle}
        aria-label={playing ? "Pause recording" : clip ? "Play the part where this was said" : "Play recording"}
        className="group relative inline-flex items-center gap-2 overflow-hidden rounded-full border border-ink/35 bg-paper py-1 pr-3.5 pl-1.5 text-sm text-ink transition-colors duration-150 hover:border-ink hover:bg-paper-2"
      >
        <span
          aria-hidden
          className="absolute inset-y-0 left-0 bg-ink/10 transition-[width] duration-200 ease-linear"
          style={{ width: `${progress * 100}%` }}
        />
        <span className="relative grid h-6 w-6 place-items-center rounded-full bg-ink text-paper">
          {playing ? <PauseIcon /> : <PlayIcon />}
        </span>
        <span className="relative font-medium">{playing ? "Playing" : "Play recording"}</span>
        {label && <span className="num relative text-[13px] text-soft">{label}</span>}
      </button>
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
    </>
  );
}

function PlayIcon() {
  return (
    <svg viewBox="0 0 20 20" className="ml-px h-3.5 w-3.5" fill="currentColor" aria-hidden>
      <path d="M6 4.2v11.6a.8.8 0 0 0 1.2.7l9.3-5.8a.8.8 0 0 0 0-1.4L7.2 3.5A.8.8 0 0 0 6 4.2Z" />
    </svg>
  );
}

function PauseIcon() {
  return (
    <svg viewBox="0 0 20 20" className="h-3.5 w-3.5" fill="currentColor" aria-hidden>
      <rect x="5" y="4" width="3.5" height="12" rx="1" />
      <rect x="11.5" y="4" width="3.5" height="12" rx="1" />
    </svg>
  );
}
