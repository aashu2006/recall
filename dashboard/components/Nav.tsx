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
            aria-current={active ? "page" : undefined}
            className={`relative rounded-md px-3 py-1.5 text-sm font-medium transition-colors duration-150 ${
              active ? "bg-raised text-ink" : "text-muted hover:bg-raised/60 hover:text-ink"
            }`}
          >
            {label}
            {active && <span className="absolute inset-x-3 -bottom-[13px] h-0.5 rounded-full bg-accent max-sm:hidden" />}
          </Link>
        );
      })}
    </nav>
  );
}
