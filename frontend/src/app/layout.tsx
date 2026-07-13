import type { Metadata } from "next";
import { IBM_Plex_Sans_Hebrew, Inter } from "next/font/google";
import { ThemeProvider } from "next-themes";
import "./globals.css";
import { AppShell } from "@/components/layout/app-shell";
import { Providers } from "@/components/providers";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

const plexHebrew = IBM_Plex_Sans_Hebrew({
  subsets: ["hebrew", "latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-hebrew",
});

export const metadata: Metadata = {
  title: "תיק השקעות · IBKR",
  description: "דשבורד תיק, יומן מסחר וניתוח ביצועים — חיבור חי לחשבון Interactive Brokers",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="he" dir="rtl" suppressHydrationWarning>
      <body className={`${inter.variable} ${plexHebrew.variable}`}>
        <ThemeProvider attribute="data-theme" defaultTheme="dark" enableSystem={false}>
          <Providers>
            <AppShell>{children}</AppShell>
          </Providers>
        </ThemeProvider>
      </body>
    </html>
  );
}
