"use client";

import { useEffect, useRef, useState } from "react";

interface Props {
  src: string | null;
  /** Clip bounds in seconds. When set, playback starts at start and stops at end. */
  start?: number | null;
  end?: number | null;
}

/**
 * Signed URLs change on every server refresh, so the first src is kept and only swapped
 * for the latest one if loading fails (e.g. the signature expired). This keeps the
 * 10 s auto refresh from restarting playback.
 */
export default function AudioPlayer({ src, start, end }: Props) {
  const [current, setCurrent] = useState(src);
  const latest = useRef(src);
  const ref = useRef<HTMLAudioElement>(null);

  useEffect(() => {
    latest.current = src;
    if (!current && src) setCurrent(src);
  }, [src, current]);

  if (!current) return <p className="text-xs text-muted">Audio not available</p>;

  const clip = start != null && end != null && end > start;
  const url = clip ? `${current}#t=${start},${end}` : current;

  return (
    <audio
      ref={ref}
      controls
      preload="none"
      src={url}
      className="h-10 w-full max-w-md"
      onError={() => {
        if (latest.current && latest.current !== current) setCurrent(latest.current);
      }}
      onPlay={() => {
        const a = ref.current;
        if (a && clip && (a.currentTime < start! || a.currentTime >= end!)) a.currentTime = start!;
      }}
      onTimeUpdate={() => {
        const a = ref.current;
        if (a && clip && a.currentTime >= end!) {
          a.pause();
          a.currentTime = start!;
        }
      }}
    />
  );
}
