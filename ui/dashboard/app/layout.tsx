import type { Metadata } from "next";
import "./globals.css";
import { Nav } from "@/components/Nav";
import { manifest } from "@/lib/manifest";

export const metadata: Metadata = {
  title: "LS-Face Study Dashboard",
  description:
    "Read-only research status for the LS-Face classical + hybrid face-recognition study: runs, results, paper coverage, and figures.",
};

// No-flash theme init: run before paint so the correct theme class is on <html>
// before first render (avoids a light->dark flicker).
const themeInit = `
(function(){try{
  var t = localStorage.getItem('theme');
  if(!t){t = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark':'light';}
  if(t === 'dark'){document.documentElement.classList.add('dark');}
}catch(e){}})();
`;

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInit }} />
      </head>
      <body className="min-h-screen antialiased">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-3 focus:z-50 focus:rounded-md focus:bg-brand focus:px-3 focus:py-1.5 focus:text-sm focus:text-white"
        >
          Skip to content
        </a>
        <Nav />
        <main id="main" className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-10">
          {children}
        </main>
        <footer className="border-t border-border">
          <div className="mx-auto flex max-w-6xl flex-col gap-1 px-4 py-6 text-xs text-faint sm:flex-row sm:items-center sm:justify-between sm:px-6">
            <span>
              LS-Face Study · classical-CV track. Read-only mirror of the repository.
            </span>
            <span>
              Data updated {manifest.study_status.updated ?? "—"} · manifest{" "}
              {manifest.generated_at.slice(0, 10)}
            </span>
          </div>
        </footer>
      </body>
    </html>
  );
}
