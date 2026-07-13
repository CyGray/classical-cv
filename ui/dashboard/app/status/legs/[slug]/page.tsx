import Link from "next/link";
import { notFound } from "next/navigation";
import { manifest, getLegBySlug, testTypeLabel } from "@/lib/manifest";
import { StatusBadge } from "@/components/StatusBadge";
import { Card } from "@/components/ui";

export function generateStaticParams() {
  return manifest.legs.map((l) => ({ slug: l.slug }));
}

function fmtBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-semibold uppercase tracking-wide text-faint">{label}</dt>
      <dd className="mt-1 text-sm text-ink">{children}</dd>
    </div>
  );
}

export default function LegDetail({ params }: { params: { slug: string } }) {
  const leg = getLegBySlug(params.slug);
  if (!leg) notFound();

  const supersededBy = leg.superseded_by
    ? manifest.legs.find((l) => l.artifact_path === leg.superseded_by)
    : undefined;

  return (
    <div className="mx-auto max-w-3xl">
      <Link
        href="/status"
        className="mb-6 inline-flex items-center gap-1 text-sm font-medium text-accent hover:underline"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
          <path d="M19 12H5M11 18l-6-6 6-6" />
        </svg>
        Back to study status
      </Link>

      <div className="mb-6 flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-bold tracking-tight text-ink">
          {leg.model} · {leg.dataset}
        </h1>
        <StatusBadge status={leg.status} />
      </div>

      <Card className="p-6">
        <dl className="grid grid-cols-2 gap-x-6 gap-y-5 sm:grid-cols-3">
          <Field label="Model">{leg.model}</Field>
          <Field label="Test type">{testTypeLabel(leg.test_type)}</Field>
          <Field label="Run date">{leg.run_date}</Field>
        </dl>

        {leg.protocol_note && (
          <div className="mt-6 border-t border-border pt-5">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-faint">
              Protocol
            </h2>
            <p className="mt-1.5 text-sm leading-relaxed text-ink">{leg.protocol_note}</p>
          </div>
        )}

        {leg.result_note && (
          <div className="mt-5">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-faint">
              Result
            </h2>
            <p className="mt-1.5 text-sm leading-relaxed text-ink">{leg.result_note}</p>
          </div>
        )}

        {supersededBy && (
          <div className="mt-5 flex items-start gap-2 rounded-lg border border-border p-3 text-sm">
            <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-500" aria-hidden />
            Superseded by{" "}
            <Link href={`/status/legs/${supersededBy.slug}`} className="font-medium text-accent hover:underline">
              {supersededBy.model} · {supersededBy.dataset}
            </Link>
            .
          </div>
        )}
      </Card>

      {/* Artifact inventory: mechanical facts, clearly separate from interpretation. */}
      <Card className="mt-5 p-6">
        <h2 className="mb-4 text-sm font-semibold text-ink">Artifact inventory</h2>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-5 sm:grid-cols-3">
          <Field label="Path">
            <code className="break-all text-xs">{leg.artifact_path}</code>
          </Field>
          <Field label="Last modified">{leg.artifact_mtime.slice(0, 10)}</Field>
          <Field label="Size">{fmtBytes(leg.artifact_size_bytes)}</Field>
        </dl>
        {leg.artifact_files.length > 0 && (
          <div className="mt-5">
            <dt className="text-xs font-semibold uppercase tracking-wide text-faint">
              Files ({leg.artifact_files.length})
            </dt>
            <dd className="mt-2 flex flex-wrap gap-1.5">
              {leg.artifact_files.map((f) => (
                <code
                  key={f}
                  className="rounded-md border border-border bg-elevated px-2 py-0.5 text-xs text-muted"
                >
                  {f}
                </code>
              ))}
            </dd>
          </div>
        )}
        <p className="mt-4 text-xs text-faint">
          Inventory is derived mechanically from the filesystem at build time. Status,
          protocol, and result above are hand-stated, never inferred from timestamps.
        </p>
      </Card>
    </div>
  );
}
