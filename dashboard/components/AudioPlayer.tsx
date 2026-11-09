"use client";

import { useEffect, useRef, useState } from "react";
import { fmtSecs } from "@/lib/format";

interface Props {
  src: string | null;
  /** Clip bounds in seconds. When set, playback starts at start and stops at end. */
  start?: number | null;
  end?: number | null;
  /** Total length, if known, so the full-call bar has a label before metadata loads. */
  duration?: number | null;
  size?: "lg" | "md";
  label?: string;
}

/**
 * Play button and progress bar over a real <audio> element (AutoRefresh checks for playing
 * <audio> to pause refreshes).
 *
 * Signed URLs change on every server refresh, so the first src is kept and only swapped
 * for the latest one if loading fails (e.g. the signature expired). This keeps the
 * 10 s auto refresh from restarting playback.
 */
export default function AudioPlayer({ src, start, end, duration, size = "md", label }: Props) {
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

  if (!current) return <p className="text-xs text-muted">Audio not available</p>;

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

  const seek = (e: React.MouseEvent<HTMLDivElement>) => {
    const a = ref.current;
    if (!a || !hi) return;
    const r = e.currentTarget.getBoundingClientRect();
    a.currentTime = lo + ((e.clientX - r.left) / r.width) * (hi - lo);
    setTime(a.currentTime);
  };

  const big = size === "lg";
  const elapsed = time != null ? Math.max(0, time - lo) : 0;

  return (
    <div className={`flex items-center gap-3 ${big ? "sm:gap-4" : ""}`}>
      <button
        type="button"
        onClick={toggle}
        aria-label={playing ? "Pause" : clip ? "Play proof clip" : "Play voice note"}
        className={`grid shrink-0 place-items-center rounded-full transition-[transform,background-color] duration-150 active:scale-95 ${
          big ? "h-12 w-12 bg-accent text-accent-ink hover:brightness-110" : "h-10 w-10 bg-raised text-ink hover:bg-line"
        }`}
      >
        {playing ? <PauseIcon /> : <PlayIcon />}
      </button>
      <div className="min-w-0 flex-1">
        {label && <p className="mb-1.5 text-xs text-muted">{label}</p>}
        <div
          onClick={seek}
          className="group relative h-2 cursor-pointer rounded-full bg-line"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(progress * 100)}
        >
          <div
            className={`absolute inset-y-0 left-0 rounded-full ${big ? "bg-accent" : "bg-muted"}`}
            style={{ width: `${progress * 100}%` }}
          />
        </div>
        <p className="mt-1.5 flex justify-between text-xs text-muted tabular-nums">
          <span>{fmtSecs(clip ? lo + elapsed : elapsed)}</span>
          <span>{clip ? `${fmtSecs(lo)}–${fmtSecs(hi)}` : hi ? fmtSecs(hi) : ""}</span>
        </p>
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

function PlayIcon() {
  return (
    <svg viewBox="0 0 20 20" className="ml-0.5 h-5 w-5" fill="currentColor" aria-hidden>
      <path d="M6 4.2v11.6a.8.8 0 0 0 1.2.7l9.3-5.8a.8.8 0 0 0 0-1.4L7.2 3.5A.8.8 0 0 0 6 4.2Z" />
    </svg>
  );
}

function PauseIcon() {
  return (
    <svg viewBox="0 0 20 20" className="h-5 w-5" fill="currentColor" aria-hidden>
      <rect x="5" y="4" width="3.5" height="12" rx="1" />
      <rect x="11.5" y="4" width="3.5" height="12" rx="1" />
    </svg>
  );
}
