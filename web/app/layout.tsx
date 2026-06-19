import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Sarvam MCP",
  description:
    "Official Sarvam AI MCP server — STT, TTS, Translate & more for Indic languages",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
