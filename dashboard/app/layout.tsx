import type { Metadata, Viewport } from "next";
import { IBM_Plex_Sans, IBM_Plex_Sans_Devanagari } from "next/font/google";
import Link from "next/link";
import AutoRefresh from "@/components/AutoRefresh";
import Nav from "@/components/Nav";
import "./globals.css";

const plex = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-plex",
  display: "swap",
});

const plexDeva = IBM_Plex_Sans_Devanagari({
  subsets: ["devanagari"],
  weight: ["400", "500", "600"],
  variable: "--font-plex-deva",
  display: "swap",
});

export const metadata: Metadata = {
  title: { default: "Recall", template: "%s · Recall" },
  description: "Live order book from WhatsApp voice notes",
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f3f4f2" },
    { media: "(prefers-color-scheme: dark)", color: "#11151a" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${plex.variable} ${plexDeva.variable}`}>
      <body className="min-h-dvh font-sans text-[15px]">
        <header className="sticky top-0 z-10 border-b border-line bg-bg/85 backdrop-blur-md">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3 sm:px-6">
            <Link href="/" className="flex items-center gap-2.5 rounded-md">
              <Mark />
              <span className="text-[17px] font-semibold tracking-tight">Recall</span>
            </Link>
            <div className="ml-auto sm:order-last">
              <AutoRefresh />
            </div>
            <div className="-mx-1 w-full sm:mx-0 sm:w-auto">
              <Nav />
            </div>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-4 pt-6 pb-16 sm:px-6 sm:pt-8">{children}</main>
      </body>
    </html>
  );
}

/** A speech bubble with a ledger line in it: what was said, written down. */
function Mark() {
  return (
    <svg viewBox="0 0 28 28" className="h-7 w-7" aria-hidden>
      <rect width="28" height="28" rx="7" className="fill-accent" />
      <path d="M8 9.5h12M8 14h8" stroke="var(--accent-ink)" strokeWidth="2.2" strokeLinecap="round" />
      <path d="M8 18.5v3.2l3.4-3.2" fill="var(--accent-ink)" />
    </svg>
  );
}
