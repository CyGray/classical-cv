import type { Metadata } from "next";
import Link from "next/link";
import { docsByGroup } from "@/lib/docs";
import { PageHeader } from "@/components/ui";

export const metadata: Metadata = {
  title: "Docs · LS-Face Dashboard",
};

export default function DocsIndex() {
  const groups = docsByGroup();
  return (
    <div>
      <PageHeader
        eyebrow="Reference"
        title="Docs & audits"
        description="Every write-up, audit, briefing, and changelog in the repository, grouped by folder and rendered with working cross-links."
      />
      <div className="space-y-8">
        {groups.map(({ group, docs }) => (
          <section key={group}>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-faint">
              {group}
            </h2>
            <div className="grid gap-2 sm:grid-cols-2">
              {docs.map((d) => (
                <Link
                  key={d.slug}
                  href={`/docs/${d.slug}`}
                  className="group flex items-center justify-between rounded-lg border border-border bg-surface px-4 py-3 transition-colors hover:border-accent/40 hover:bg-elevated/40"
                >
                  <span className="font-medium text-ink group-hover:text-accent">
                    {d.title}
                  </span>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-faint group-hover:text-accent" aria-hidden>
                    <path d="M9 6l6 6-6 6" />
                  </svg>
                </Link>
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
