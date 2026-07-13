import Link from "next/link";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-md py-20 text-center">
      <p className="font-serif text-5xl font-semibold text-ink">404</p>
      <h1 className="mt-4 text-xl font-semibold text-ink">Page not found</h1>
      <p className="mt-2 text-muted">
        That route isn’t part of the dashboard. It may have been renamed or the data
        rebuilt.
      </p>
      <Link
        href="/"
        className="mt-6 inline-flex items-center gap-1 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:opacity-90"
      >
        Back to overview
      </Link>
    </div>
  );
}
