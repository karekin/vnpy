import { Outfit } from "next/font/google";
import "./globals.css";
import "swiper/swiper-bundle.css";
import "simplebar-react/dist/simplebar.min.css";
import { SidebarProvider } from "@/context/SidebarContext";
import { ThemeProvider } from "@/context/ThemeContext";
import { AuthProvider } from "@/context/AuthContext";
import { TenantProvider } from "@/context/TenantContext";
import { PermissionProvider } from "@/context/PermissionContext";
import { TenantThemeProvider } from "@/components/layout/TenantThemeProvider";
import type { Metadata, Viewport } from "next";
import PwaRuntime from "@/components/openclaw-mobile/PwaRuntime";

const outfit = Outfit({
  subsets: ["latin"],
});

export const metadata: Metadata = {
  applicationName: "OpenClaw",
  appleWebApp: {
    capable: true,
    title: "OpenClaw",
    statusBarStyle: "black-translucent",
  },
  icons: {
    icon: [
      { url: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
      { url: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
    apple: [{ url: "/icons/apple-touch-icon.png", sizes: "180x180", type: "image/png" }],
  },
  manifest: "/manifest.webmanifest",
  title: {
    default: "OpenClaw Investment Dashboard",
    template: "%s",
  },
};

export const viewport: Viewport = {
  themeColor: "#101828",
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body className={`${outfit.className} dark:bg-gray-900`}>
        <AuthProvider>
          <TenantProvider>
            <PermissionProvider>
              <ThemeProvider>
                <TenantThemeProvider>
                  <SidebarProvider>
                    <PwaRuntime />
                    {children}
                  </SidebarProvider>
                </TenantThemeProvider>
              </ThemeProvider>
            </PermissionProvider>
          </TenantProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
