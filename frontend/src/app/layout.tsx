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

const outfit = Outfit({
  subsets: ["latin"],
});

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${outfit.className} dark:bg-gray-900`}>
        <AuthProvider>
          <TenantProvider>
            <PermissionProvider>
              <ThemeProvider>
                <TenantThemeProvider>
                  <SidebarProvider>{children}</SidebarProvider>
                </TenantThemeProvider>
              </ThemeProvider>
            </PermissionProvider>
          </TenantProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
