import "./globals.css";
import "katex/dist/katex.min.css";
import type { Metadata } from "next";
import NavBar from "./NavBar";
import LicenseGuard from "./LicenseGuard";
import OnboardingTour from "./OnboardingTour";
import { ModeProvider } from "@/lib/mode";
import { LicenseProvider } from "@/lib/license";
import { TourProvider } from "@/lib/tour";

export const metadata: Metadata = {
  title: "Quant-OS",
  description: "Quant-OS research & trading dashboard",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-zinc-950 text-zinc-100 antialiased">
        <LicenseProvider>
          <LicenseGuard>
            <ModeProvider>
              <TourProvider>
                <NavBar />
                {children}
                <OnboardingTour />
              </TourProvider>
            </ModeProvider>
          </LicenseGuard>
        </LicenseProvider>
      </body>
    </html>
  );
}
