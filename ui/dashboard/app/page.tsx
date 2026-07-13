import Link from "next/link";
import { manifest } from "@/lib/manifest";
import { CardLink } from "@/components/ui";

function Stat({ value, label, tone }: { value: number | string; label: string; tone: string }) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4 text-center shadow-card">
      <div className={`text-2xl font-bold ${tone}`}>{value}</div>
      <div className="mt-0.5 text-xs font-medium text-muted">{label}</div>
    </div>
  );
}

export default function Home() {
  const legs = manifest.legs;
  const done = legs.filter((l) => l.status === "done").length;
  const open = legs.filter((l) => l.status === "open").length;
  const superseded = legs.filter((l) => l.status === "superseded").length;
  const paperTodo = manifest.paper_sections.filter(
    (s) => s.state !== "current",
  ).length;
  const hf = manifest.study_status.headline_finding;

  return (
    <div className="space-y-10">
      {/* Hero */}
      <section>
        <p className="text-xs font-semibold uppercase tracking-wider text-brand">
          Research status dashboard
        </p>
        <h1 className="mt-2 max-w-3xl text-3xl font-bold tracking-tight text-ink sm:text-4xl">
          Where the LS-Face study actually stands — runs, results, and paper coverage
          in one place.
        </h1>
        <p className="mt-3 max-w-2xl text-muted">
          A read-only mirror of the repository, so anyone on the team or an advisor can
          see what has been run and what the paper still needs — without opening a
          terminal or reading raw <code className="rounded bg-elevated px-1 py-0.5 text-sm">reports/</code> output.
        </p>
      </section>

      {/* Headline finding banner */}
      {hf?.active && (
        <section
          aria-labelledby="headline-finding"
          className="relative overflow-hidden rounded-2xl border border-amber-300/60 bg-gradient-to-br from-amber-50 to-orange-50 p-6 dark:border-amber-500/30 dark:from-amber-500/10 dark:to-orange-500/5"
        >
          <div className="flex items-start gap-3">
            <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-amber-500/20 text-amber-600 dark:text-amber-300">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                <path d="M12 9v4M12 17h.01" />
                <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
              </svg>
            </span>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-amber-700 dark:text-amber-300">
                Headline finding
              </p>
              <h2 id="headline-finding" className="mt-1 text-lg font-bold text-ink">
                {hf.title}
              </h2>
              <p className="mt-2 max-w-3xl text-sm leading-relaxed text-ink/80 dark:text-ink/70">
                {hf.summary}
              </p>
              {hf.source_doc && (
                <Link
                  href="/docs/audits/state-07-10"
                  className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-brand hover:underline"
                >
                  Read the source audit
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
                    <path d="M5 12h14M13 6l6 6-6 6" />
                  </svg>
                </Link>
              )}
            </div>
          </div>
        </section>
      )}

      {/* Quick stats */}
      <section>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat value={done} label="Legs done" tone="text-emerald-600 dark:text-emerald-400" />
          <Stat value={open} label="Legs open" tone="text-rose-600 dark:text-rose-400" />
          <Stat value={superseded} label="Superseded" tone="text-slate-500" />
          <Stat value={paperTodo} label="Paper sections to fix" tone="text-amber-600 dark:text-amber-400" />
        </div>
      </section>

      {/* Section navigation */}
      <section>
        <h2 className="mb-4 text-lg font-semibold tracking-tight text-ink">
          Explore
        </h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <CardLink
            href="/status"
            title="Study status"
            description="Per-leg run table, the master checklist, and how each paper section tracks the data."
            icon={<IconChart />}
          />
          <CardLink
            href="/paper"
            title="Paper viewer"
            description="The draft rendered in full, with a live sidebar showing which sections are stale or ready."
            icon={<IconDoc />}
          />
          <CardLink
            href="/docs"
            title="Docs & audits"
            description="Every write-up, audit, and briefing, grouped by folder and cross-linked."
            icon={<IconBook />}
          />
          <CardLink
            href="/figures"
            title="Figures gallery"
            description="All tracked figures across benchmarks, independence tests, and presentations."
            icon={<IconImage />}
          />
        </div>
      </section>
    </div>
  );
}

function IconChart() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M3 3v18h18" />
      <path d="M7 15l3-4 3 2 4-6" />
    </svg>
  );
}
function IconDoc() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6M9 13h6M9 17h6" />
    </svg>
  );
}
function IconBook() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
      <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
    </svg>
  );
}
function IconImage() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <circle cx="9" cy="9" r="2" />
      <path d="m21 15-3.6-3.6a2 2 0 0 0-2.8 0L6 21" />
    </svg>
  );
}
