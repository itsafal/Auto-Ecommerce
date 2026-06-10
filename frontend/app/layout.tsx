import "./globals.css";
import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";
import type { ReactNode } from "react";

// Real terminal typography: IBM Plex Mono carries the operator-console data
// surfaces; IBM Plex Sans handles prose. Exposed as CSS variables so the
// `console` theme tokens (globals.css) and per-store themes can opt in.
const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-mono"
});

const plexSans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-sans"
});

export const metadata: Metadata = {
  title: "Auto-Ecommerce // Operator Console",
  description:
    "Autonomous AI agents that discover, score, and launch single-product storefronts."
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className={`${plexMono.variable} ${plexSans.variable}`}>{children}</body>
    </html>
  );
}
