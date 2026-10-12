import type { Metadata } from "next";
import { Fraunces, Inter, JetBrains_Mono, Source_Sans_3 } from "next/font/google";
import "./globals.css";

const display = Fraunces({ variable: "--f-display", subsets: ["latin"], axes: ["opsz"] });
const sans = Inter({ variable: "--f-sans", subsets: ["latin"] });
const page = Source_Sans_3({ variable: "--f-page", subsets: ["latin"] });
const mono = JetBrains_Mono({ variable: "--f-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "FairHire — a resume every parser can read",
  description:
    "Upload your resume, see exactly what an applicant tracking system reads, and fix what it can't — live, with the same answer every time.",
};

/** Applies a saved theme before first paint so the page never flashes the wrong one. */
const THEME_INIT = `try{var t=localStorage.getItem("fairhire:theme");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t}catch(e){}`;

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning className={`${display.variable} ${sans.variable} ${page.variable} ${mono.variable}`}>
      <head><script dangerouslySetInnerHTML={{ __html: THEME_INIT }} /></head>
      <body>{children}</body>
    </html>
  );
}
