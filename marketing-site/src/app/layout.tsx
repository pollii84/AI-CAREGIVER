import type { Metadata } from "next";
import { Figtree, Noto_Sans } from "next/font/google";
import "./globals.css";

// Figtree (heading) + Noto Sans (body) — Product/UX doc §1 typography choice:
// high-legibility, wide-language-support faces, matters for Dynamic Type
// scaling and future AD/MS localization.
const figtree = Figtree({
  variable: "--font-figtree",
  subsets: ["latin"],
  weight: ["500", "600", "700"],
});

const notoSans = Noto_Sans({
  variable: "--font-noto-sans",
  subsets: ["latin"],
  weight: ["400", "500", "700"],
});

export const metadata: Metadata = {
  title: "AI Caregiver — Support for Parkinson's, Alzheimer's & MS",
  description:
    "Daily symptom tracking, medication reminders, and an AI care agent for patients with neurodegenerative disease and the people who care for them. Not a diagnostic tool — built to raise quality of life, every day.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${figtree.variable} ${notoSans.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
