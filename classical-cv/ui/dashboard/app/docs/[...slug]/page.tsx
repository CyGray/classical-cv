import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getAllDocSlugs, getDocBySlug } from "@/lib/docs";
import { Markdown } from "@/components/Markdown";

export function generateStaticParams() {
  return getAllDocSlugs().map((slug) => ({ slug: slug.split("/") }));
}

export function generateMetadata({
  params,
}: {
  params: { slug: string[] };
}): Metadata {
  const doc = getDocBySlug(params.slug.join("/"));
  return { title: doc ? `${doc.entry.title} · LS-Face Dashboard` : "Doc not found" };
}

export default function DocPage({ params }: { params: { slug: string[] } }) {
  const slug = params.slug.join("/");
  const doc = getDocBySlug(slug);
  if (!doc) notFound();

  return (
    <article className="mx-auto max-w-prose">
      <Link
        href="/docs"
        className="mb-6 inline-flex items-center gap-1 text-sm font-medium text-accent hover:underline"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
          <path d="M19 12H5M11 18l-6-6 6-6" />
        </svg>
        All docs
      </Link>
      <p className="mb-2 font-mono text-xs font-medium uppercase tracking-wide text-muted">
        {doc.entry.group}
      </p>
      <Markdown>{doc.content}</Markdown>
    </article>
  );
}
