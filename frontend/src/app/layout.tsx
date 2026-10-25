import type { Metadata } from "next";
import { Lato, Roboto } from "next/font/google";
import { AppRouterCacheProvider } from "@mui/material-nextjs/v15-appRouter";
import { AppProviders } from "@/components/AppProviders";
import "./globals.css";

// Self-hosted at build time by next/font: no runtime request to Google.
const lato = Lato({ subsets: ["latin"], weight: ["400", "700"], variable: "--font-lato", display: "swap" });
const roboto = Roboto({ subsets: ["latin"], weight: ["400", "500"], variable: "--font-roboto", display: "swap" });

export const metadata: Metadata = {
  title: "Candidate communication",
  description: "Message candidates individually or in bulk and track every delivery.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${lato.variable} ${roboto.variable}`}>
      <body>
        <AppRouterCacheProvider>
          <AppProviders>{children}</AppProviders>
        </AppRouterCacheProvider>
      </body>
    </html>
  );
}
