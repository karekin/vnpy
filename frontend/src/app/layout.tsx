import type { Metadata } from "next";
import { Rajdhani, Noto_Sans_SC } from "next/font/google";
import "./globals.css";

const displayFont = Rajdhani({
  variable: "--font-display",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const textFont = Noto_Sans_SC({
  variable: "--font-text",
  subsets: ["latin"],
  weight: ["400", "500", "700"],
});

export const metadata: Metadata = {
  title: "VeighNa Web Workstation",
  description: "Next.js frontend workstation for vn.py style trading operations.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body className={`${displayFont.variable} ${textFont.variable}`}>{children}</body>
    </html>
  );
}
