import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "FairHire — Deterministic resume–JD match",
  description:
    "Deterministic NER-style resume parsing and JD matching with visual connecting lines. Rule-based; no LLM decides whether a match exists.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} bg-[var(--base)]`}
    >
      <body className="min-h-dvh antialiased">{children}</body>
    </html>
  );
}
