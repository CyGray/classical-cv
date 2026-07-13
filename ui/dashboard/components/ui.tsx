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
    <div className={`rounded-lg border border-border bg-surface ${className}`}>
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
        <p className="mb-1.5 font-mono text-xs font-medium uppercase tracking-wider text-muted">
          {eyebrow}
        </p>
      )}
      <h1 className="font-serif text-2xl font-semibold tracking-tight text-ink sm:text-3xl">
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
      className="group block rounded-lg border border-border bg-surface p-5 transition-colors hover:border-accent/50 hover:bg-elevated"
    >
      <div className="flex items-center gap-3">
        {icon && (
          <span className="flex h-8 w-8 items-center justify-center rounded-md border border-border text-ink">
            {icon}
          </span>
        )}
        <h3 className="font-semibold text-ink group-hover:text-accent">{title}</h3>
      </div>
      <p className="mt-2 text-sm text-muted">{description}</p>
    </Link>
  );
}
