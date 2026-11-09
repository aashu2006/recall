"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { TableBody } from "@/components/ui/table";

/**
 * Table body that briefly turns a row light blue when auto refresh brings a change for it.
 * Rows carry data-flash-id and data-flash-version. The first render only records them, so
 * opening the page doesn't flash; later renders (router.refresh keeps this component mounted)
 * flash any row whose version changed or that is new.
 */
export default function FlashBody({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLTableSectionElement>(null);
  const seen = useRef<Map<string, string> | null>(null);

  useEffect(() => {
    const rows = ref.current?.querySelectorAll<HTMLTableRowElement>("tr[data-flash-id]") ?? [];
    const prev = seen.current;
    const next = new Map<string, string>();
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    for (const row of rows) {
      const id = row.dataset.flashId!;
      const version = row.dataset.flashVersion ?? "";
      next.set(id, version);
      if (prev && prev.get(id) !== version && !reduce) {
        row.animate([{ backgroundColor: "oklch(0.94 0.04 255)" }, { backgroundColor: "transparent" }], {
          duration: 2000,
          easing: "ease-out",
        });
      }
    }
    seen.current = next;
  });

  return <TableBody ref={ref}>{children}</TableBody>;
}
