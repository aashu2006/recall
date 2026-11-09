import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono, Noto_Sans_Devanagari } from "next/font/google";
import Link from "next/link";
import AutoRefresh from "@/components/AutoRefresh";
import Nav from "@/components/Nav";
import "./globals.css";

const geist = Geist({ subsets: ["latin"], variable: "--font-geist-sans", display: "swap" });
const geistMono = Geist_Mono({ subsets: ["latin"], variable: "--font-geist-mono", display: "swap" });
const notoDeva = Noto_Sans_Devanagari({
  subsets: ["devanagari"],
  weight: ["400", "500", "600"],
  variable: "--font-noto-deva",
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
  themeColor: "#ffffff",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${geist.variable} ${geistMono.variable} ${notoDeva.variable}`}>
      <body className="min-h-dvh">
        <header className="sticky top-0 z-20 border-b bg-background">
          <div className="mx-auto flex h-12 max-w-6xl items-center gap-6 px-4 sm:px-6">
            <Link href="/" className="font-semibold">
              Recall
            </Link>
            <Nav />
            <div className="ml-auto">
              <AutoRefresh />
            </div>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">{children}</main>
      </body>
    </html>
  );
}
