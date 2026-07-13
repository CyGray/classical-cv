import Link from "next/link";
import type { ReactNode } from "react";

export function Card({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-xl border border-border bg-surface shadow-card ${className}`}
    >
      {children}
    </div>
  );
}

export function PageHeader({
  eyebrow,
  title,
  description,
}: {
  eyebrow?: string;
  title: string;
  description?: ReactNode;
}) {
  return (
    <div className="mb-8">
      {eyebrow && (
        <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-brand">
          {eyebrow}
        </p>
      )}
      <h1 className="text-2xl font-bold tracking-tight text-ink sm:text-3xl">
        {title}
      </h1>
      {description && (
        <p className="mt-2 max-w-prose text-muted">{description}</p>
      )}
    </div>
  );
}

export function SectionTitle({
  children,
  id,
}: {
  children: ReactNode;
  id?: string;
}) {
  return (
    <h2 id={id} className="mb-3 text-lg font-semibold tracking-tight text-ink">
      {children}
    </h2>
  );
}

export function Pill({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-md border border-border bg-elevated px-2 py-0.5 text-xs font-medium text-muted">
      {children}
    </span>
  );
}

export function CardLink({
  href,
  title,
  description,
  icon,
}: {
  href: string;
  title: string;
  description: string;
  icon?: ReactNode;
}) {
  return (
    <Link
      href={href}
      className="group block rounded-xl border border-border bg-surface p-5 shadow-card transition-all hover:-translate-y-0.5 hover:border-brand/40 hover:shadow-md"
    >
      <div className="flex items-center gap-3">
        {icon && (
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-soft text-brand">
            {icon}
          </span>
        )}
        <h3 className="font-semibold text-ink group-hover:text-brand">{title}</h3>
      </div>
      <p className="mt-2 text-sm text-muted">{description}</p>
    </Link>
  );
}
