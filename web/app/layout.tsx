import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MADQAQ Sentinel — Dual-Channel Procedure Integrity",
  description: "Local finalist demonstration prototype. The digital channel is simulated.",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
