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
      className="flex items-center gap-2 text-sm text-soft"
      title={paused ? "Updates pause while a recording plays" : "Updates every 10 seconds"}
    >
      <span className={`h-2 w-2 rounded-full ${paused ? "bg-red" : "bg-green motion-safe:animate-pulse"}`} />
      {paused ? "Paused" : "Live"}
    </span>
  );
}
