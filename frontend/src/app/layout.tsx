"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import Link from "next/link";
import "./globals.css";

const navItems = [
  { href: "/chat",   label: "Chat"   },
  { href: "/evals",  label: "Evals"  },
  { href: "/traces", label: "Traces" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient());

  return (
    <html lang="en" className="dark">
      <body className="flex h-screen bg-slate-950 text-slate-100 overflow-hidden">
        <QueryClientProvider client={queryClient}>
          <nav className="w-48 flex-shrink-0 bg-slate-900 border-r border-slate-800 flex flex-col py-6 px-3 gap-1">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider px-3 mb-3">
              RAG Platform
            </span>
            {navItems.map(({ href, label }) => (
              <Link
                key={href}
                href={href}
                className="px-3 py-2 rounded-lg text-sm text-slate-300 hover:bg-slate-800 hover:text-white transition-colors"
              >
                {label}
              </Link>
            ))}
          </nav>
          <main className="flex-1 overflow-hidden">{children}</main>
        </QueryClientProvider>
      </body>
    </html>
  );
}
