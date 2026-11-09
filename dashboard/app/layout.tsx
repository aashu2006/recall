import type { Metadata, Viewport } from "next";
import { IBM_Plex_Sans, IBM_Plex_Sans_Devanagari, IBM_Plex_Serif } from "next/font/google";
import Link from "next/link";
import AutoRefresh from "@/components/AutoRefresh";
import Nav from "@/components/Nav";
import "./globals.css";

const plex = IBM_Plex_Sans({ subsets: ["latin"], weight: ["400", "500", "600"], variable: "--font-plex", display: "swap" });
const plexDeva = IBM_Plex_Sans_Devanagari({
  subsets: ["devanagari"],
  weight: ["400", "500", "600"],
  variable: "--font-plex-deva",
  display: "swap",
});
const plexSerif = IBM_Plex_Serif({ subsets: ["latin"], weight: ["500", "600"], variable: "--font-plex-serif", display: "swap" });

export const metadata: Metadata = {
  title: { default: "Recall", template: "%s · Recall" },
  description: "Live order register from WhatsApp voice notes",
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#f1ead9",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${plex.variable} ${plexDeva.variable} ${plexSerif.variable}`}>
      <body className="min-h-dvh font-sans text-[15px]">
        <header className="sticky top-0 z-20 border-b border-rule bg-paper-2/95 backdrop-blur-sm">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-10 px-4 sm:flex-nowrap sm:px-8">
            <Link href="/" className="flex items-center gap-3 rounded py-3.5" aria-label="Recall, order register">
              <Mark />
              <span className="flex items-baseline gap-2.5">
                <span className="font-serif text-[21px] leading-none font-semibold tracking-tight">Recall</span>
                <span lang="hi" className="hidden text-[13px] leading-none text-soft md:inline">
                  ऑर्डर बही
                </span>
              </span>
            </Link>
            <div className="ml-auto sm:order-last">
              <AutoRefresh />
            </div>
            <div className="w-full self-stretch sm:w-auto">
              <Nav />
            </div>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-4 pt-8 pb-24 sm:px-8 sm:pt-12">{children}</main>
      </body>
    </html>
  );
}

/** A register page: ink frame, red margin line, two ruled lines. */
function Mark() {
  return (
    <svg viewBox="0 0 24 24" className="h-[22px] w-[22px] shrink-0" aria-hidden>
      <rect x="2.5" y="2.5" width="19" height="19" rx="3" fill="var(--paper-3)" stroke="var(--ink)" strokeWidth="1.6" />
      <path d="M8 3v18" stroke="var(--red)" strokeWidth="1.4" />
      <path d="M10.5 9.5h7M10.5 14.5h5" stroke="var(--ink)" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}
