import "./globals.css";
import type { Metadata } from "next";
import Link from "next/link";

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
        <header className="border-b border-zinc-800">
          <nav className="mx-auto flex max-w-6xl items-center gap-6 px-8 py-4">
            <Link href="/" className="text-sm font-semibold tracking-tight">
              Quant-OS
            </Link>
            <Link href="/" className="text-sm text-zinc-400 hover:text-zinc-100">
              Strategies
            </Link>
            <Link href="/ideas" className="text-sm text-zinc-400 hover:text-zinc-100">
              Research Hub
            </Link>
          </nav>
        </header>
        {children}
      </body>
    </html>
  );
}
