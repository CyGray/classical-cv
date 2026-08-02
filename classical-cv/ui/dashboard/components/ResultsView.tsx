import { resultGroups, type ResultTest } from "@/lib/results";
import { VerdictBadge } from "./StatusBadge";
import { Card } from "./ui";

function TestCard({ test }: { test: ResultTest }) {
  return (
    <Card className="p-5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h3 className="font-semibold text-ink">{test.name}</h3>
        <VerdictBadge verdict={test.verdict} />
      </div>
      <p className="mt-1.5 text-sm text-muted">{test.question}</p>

      {test.method && (
        <p className="mt-3 rounded-md border border-border bg-elevated px-3 py-2 font-mono text-xs leading-relaxed text-muted">
          {test.method}
        </p>
      )}

      <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3">
        {test.stats.map((s, i) => (
          <div key={i}>
            <dt className="text-xs text-faint">{s.label}</dt>
            <dd className="mt-0.5 font-mono text-base font-semibold tabular-nums text-ink">
              {s.value}
              {s.ci && <span className="ml-1 text-xs font-normal text-faint">{s.ci}</span>}
            </dd>
            {s.note && <dd className="mt-0.5 text-xs leading-snug text-muted">{s.note}</dd>}
          </div>
        ))}
      </dl>

      {test.comparison && (
        <p className="mt-4 border-t border-border pt-3 text-sm leading-relaxed text-muted">
          <span className="font-medium text-ink">Comparison. </span>
          {test.comparison}
        </p>
      )}

      <p className="mt-3 text-sm leading-relaxed text-ink">
        <span className="font-medium">Means. </span>
        {test.conclusion}
      </p>

      <p className="mt-3 font-mono text-xs text-faint">{test.source}</p>
    </Card>
  );
}

export function ResultsView() {
  return (
    <div className="lg:grid lg:grid-cols-[10rem_1fr] lg:gap-10">
      <nav
        aria-label="Result groups"
        className="mb-8 flex flex-wrap gap-2 text-sm lg:mb-0 lg:sticky lg:top-20 lg:flex lg:h-fit lg:flex-col lg:gap-1"
      >
        {resultGroups.map((g) => (
          <a
            key={g.id}
            href={`#${g.id}`}
            className="rounded-md border border-border px-2.5 py-1 text-muted transition-colors hover:border-accent/50 hover:text-ink lg:border-0 lg:px-0 lg:py-0.5"
          >
            {g.title}
          </a>
        ))}
      </nav>

      <div className="space-y-12">
        {resultGroups.map((g) => (
          <section key={g.id} id={g.id} className="scroll-mt-20">
            <h2 className="font-serif text-xl font-semibold tracking-tight text-ink">
              {g.title}
            </h2>
            {g.intro && <p className="mt-1.5 max-w-prose text-sm text-muted">{g.intro}</p>}
            <div className="mt-5 grid gap-4 md:grid-cols-2">
              {g.tests.map((t) => (
                <TestCard key={t.id} test={t} />
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
