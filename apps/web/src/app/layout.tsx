import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PerfMind AI",
  description: "Autonomous frontend performance monitoring agent",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
