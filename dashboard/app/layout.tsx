import type { Metadata, Viewport } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans, IBM_Plex_Sans_Devanagari, IBM_Plex_Serif } from "next/font/google";
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
const plexMono = IBM_Plex_Mono({ subsets: ["latin"], weight: ["400", "500"], variable: "--font-plex-mono", display: "swap" });

export const metadata: Metadata = {
  title: { default: "Recall", template: "%s · Recall" },
  description: "Live order register from WhatsApp voice notes",
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#f2ecdc",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${plex.variable} ${plexDeva.variable} ${plexSerif.variable} ${plexMono.variable}`}>
      <body className="min-h-dvh font-sans text-[15px]">
        <header className="sticky top-0 z-10 border-b border-ink/25 bg-paper-2/95 backdrop-blur-sm">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-8 gap-y-1 px-4 pt-3 sm:px-6">
            <Link href="/" className="flex items-baseline gap-2.5 rounded pb-3 sm:pb-3.5">
              <span className="font-serif text-[22px] leading-none font-semibold tracking-tight">Recall</span>
              <span className="text-sm text-soft">Order register</span>
            </Link>
            <div className="ml-auto pb-3 sm:order-last sm:pb-3.5">
              <AutoRefresh />
            </div>
            <div className="w-full sm:w-auto sm:self-end">
              <Nav />
            </div>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-4 pt-7 pb-20 sm:px-6 sm:pt-10">{children}</main>
      </body>
    </html>
  );
}
