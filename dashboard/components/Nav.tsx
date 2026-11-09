"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Orders" },
  { href: "/calls", label: "Calls" },
  { href: "/pending", label: "Pending" },
];

export default function Nav() {
  const path = usePathname();
  return (
    <nav className="flex gap-1">
      {LINKS.map(({ href, label }) => {
        const active = href === "/" ? path === "/" || path.startsWith("/orders") : path.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
              active ? "bg-ink text-bg" : "text-muted hover:bg-line/60 hover:text-ink"
            }`}
          >
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
