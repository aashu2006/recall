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
    <span className="hidden text-[13px] text-muted-foreground sm:inline" title="Refreshes every 10 seconds, paused while audio plays">
      {paused ? "Auto-refresh paused" : "Auto-refresh on"}
    </span>
  );
}
