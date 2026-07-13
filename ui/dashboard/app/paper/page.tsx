import type { Metadata } from "next";
import { getDocBySlug } from "@/lib/docs";
import { manifest } from "@/lib/manifest";
import { Markdown } from "@/components/Markdown";
import { PaperStateBadge } from "@/components/StatusBadge";

export const metadata: Metadata = {
  title: "Paper · LS-Face Dashboard",
};

export default function PaperPage() {
  const doc = getDocBySlug("paper");
  const sections = manifest.paper_sections;

  return (
    <div className="lg:grid lg:grid-cols-[1fr_18rem] lg:gap-10">
      <article className="max-w-prose">
        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-brand">
          Draft manuscript
        </p>
        {doc ? (
          <Markdown>{doc.content}</Markdown>
        ) : (
          <p className="text-muted">Paper source not found in the manifest content.</p>
        )}
      </article>

      {/* Coverage sidebar — how each section tracks the data. */}
      <aside className="mt-10 lg:mt-0">
        <div className="lg:sticky lg:top-20">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-faint">
            Section coverage
          </h2>
          <div className="space-y-2">
            {sections.map((s, i) => (
              <div
                key={i}
                className="rounded-lg border border-border bg-surface p-3 shadow-card"
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="text-sm font-medium text-ink">{s.section}</span>
                  <PaperStateBadge state={s.state} />
                </div>
                <p className="mt-1.5 text-xs leading-relaxed text-muted">{s.needed}</p>
              </div>
            ))}
          </div>
          <p className="mt-4 text-xs text-faint">
            Coverage is hand-maintained alongside the runs it describes — the whole point
            is to keep the paper from silently lagging the data.
          </p>
        </div>
      </aside>
    </div>
  );
}
