"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { ThemeToggle } from "./ThemeToggle";

const LINKS = [
  { href: "/", label: "Overview" },
  { href: "/results", label: "Results" },
  { href: "/status", label: "Study status" },
  { href: "/paper", label: "Paper" },
  { href: "/docs", label: "Docs" },
  { href: "/figures", label: "Figures" },
];

function isActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(href + "/");
}

export function Nav() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-surface/85 backdrop-blur supports-[backdrop-filter]:bg-surface/70">
      <div className="mx-auto flex h-14 max-w-6xl items-center gap-4 px-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2 font-serif font-semibold tracking-tight text-ink">
          <span className="flex h-7 w-7 items-center justify-center rounded-md border border-border text-sm font-semibold">
            LS
          </span>
          <span className="hidden sm:inline">Face Study</span>
        </Link>

        <nav className="hidden flex-1 items-center gap-1 md:flex" aria-label="Primary">
          {LINKS.map((l) => {
            const active = isActive(pathname, l.href);
            return (
              <Link
                key={l.href}
                href={l.href}
                aria-current={active ? "page" : undefined}
                className={`border-b-2 px-3 py-1.5 text-sm font-medium transition-colors ${
                  active
                    ? "border-accent text-ink"
                    : "border-transparent text-muted hover:border-border hover:text-ink"
                }`}
              >
                {l.label}
              </Link>
            );
          })}
        </nav>

        <div className="ml-auto flex items-center gap-2 md:ml-0">
          <ThemeToggle />
          <button
            type="button"
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-border text-muted md:hidden"
            aria-label="Toggle navigation"
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
              {open ? <path d="M6 6l12 12M18 6L6 18" /> : <path d="M4 7h16M4 12h16M4 17h16" />}
            </svg>
          </button>
        </div>
      </div>

      {open && (
        <nav className="border-t border-border bg-surface px-4 py-2 md:hidden" aria-label="Mobile">
          {LINKS.map((l) => {
            const active = isActive(pathname, l.href);
            return (
              <Link
                key={l.href}
                href={l.href}
                onClick={() => setOpen(false)}
                className={`block rounded-lg px-3 py-2 text-sm font-medium ${
                  active ? "bg-elevated text-ink" : "text-muted hover:bg-elevated"
                }`}
              >
                {l.label}
              </Link>
            );
          })}
        </nav>
      )}
    </header>
  );
}
