import "./globals.css";
import type { Metadata } from "next";
import { Manrope, Playfair_Display } from "next/font/google";
import type { ReactNode } from "react";

const bodyFont = Manrope({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
  variable: "--font-body",
});

const displayFont = Playfair_Display({
  subsets: ["latin"],
  weight: ["600", "700"],
  variable: "--font-display",
});

export const metadata: Metadata = {
  title: "TreGo Capital | Credit Intelligence & Advisory",
  description:
    "TreGo Capital helps corporates, CAs, and financial advisors simulate ratings, improve credit readiness, unlock TReDS access, and prepare for listing conversations.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className="scroll-smooth">
      <body className={`${bodyFont.variable} ${displayFont.variable} bg-cloud font-sans text-ink antialiased`}>
        {children}
      </body>
    </html>
  );
}
