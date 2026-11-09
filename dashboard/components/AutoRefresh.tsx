"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

const INTERVAL_MS = 10_000;

/** Re-runs the server components every 10 s. Skips while the tab is hidden or audio is playing. */
export default function AutoRefresh() {
  const router = useRouter();
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    const id = setInterval(() => {
      const playing = [...document.querySelectorAll("audio")].some((a) => !a.paused);
      setPaused(playing);
      if (document.hidden || playing) return;
      router.refresh();
    }, INTERVAL_MS);
    return () => clearInterval(id);
  }, [router]);

  return (
    <span
      className="flex items-center gap-2 rounded-full border border-line px-2.5 py-1 text-xs text-muted"
      title={paused ? "Updates pause while audio plays" : "Updates every 10 seconds"}
    >
      <span className="relative flex h-2 w-2">
        {!paused && (
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-now opacity-50 motion-reduce:hidden" />
        )}
        <span className={`relative inline-flex h-2 w-2 rounded-full ${paused ? "bg-accent" : "bg-now"}`} />
      </span>
      {paused ? "Paused" : "Live"}
    </span>
  );
}
