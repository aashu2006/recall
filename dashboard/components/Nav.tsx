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
    <nav className="-mb-px flex gap-6">
      {LINKS.map(({ href, label }) => {
        const active = href === "/" ? path === "/" || path.startsWith("/orders") : path.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={`border-b-2 pb-2.5 text-[15px] transition-colors duration-150 sm:pb-3.5 ${
              active ? "border-ink font-medium text-ink" : "border-transparent text-soft hover:border-rule hover:text-ink"
            }`}
          >
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
