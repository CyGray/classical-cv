"use client";

import { useMemo, useState } from "react";
import type { Figure } from "@/lib/manifest";

const GROUP_LABELS: Record<string, string> = {
  docs: "Hybrid figures",
  reports: "Core report figures",
  battery: "Complementarity battery",
  independence: "Independence expansion",
};

export function FiguresGallery({ figures }: { figures: Figure[] }) {
  const [query, setQuery] = useState("");
  const [group, setGroup] = useState<string>("all");
  const [active, setActive] = useState<Figure | null>(null);

  const groups = useMemo(
    () => Array.from(new Set(figures.map((f) => f.group))),
    [figures],
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return figures.filter(
      (f) =>
        (group === "all" || f.group === group) &&
        (q === "" || f.label.toLowerCase().includes(q) || f.src.toLowerCase().includes(q)),
    );
  }, [figures, query, group]);

  return (
    <div>
      {/* Controls */}
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-faint" aria-hidden>
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.3-4.3" />
          </svg>
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filter by name (e.g. fig_hybrid, mcnemar, roc)…"
            aria-label="Filter figures"
            className="w-full rounded-lg border border-border bg-surface py-2 pl-9 pr-3 text-sm text-ink placeholder:text-faint focus:border-accent focus:outline-none"
          />
        </div>
        <div className="flex flex-wrap gap-1">
          <FilterChip active={group === "all"} onClick={() => setGroup("all")}>
            All
          </FilterChip>
          {groups.map((g) => (
            <FilterChip key={g} active={group === g} onClick={() => setGroup(g)}>
              {GROUP_LABELS[g] ?? g}
            </FilterChip>
          ))}
        </div>
      </div>

      <p className="mb-4 text-sm text-muted">
        {filtered.length} figure{filtered.length === 1 ? "" : "s"}
      </p>

      {filtered.length === 0 ? (
        <p className="rounded-lg border border-dashed border-border py-12 text-center text-sm text-faint">
          No figures match that filter.
        </p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((f) => (
            <button
              key={f.file}
              onClick={() => setActive(f)}
              className="group overflow-hidden rounded-lg border border-border bg-surface text-left transition-colors hover:border-accent/40"
            >
              <div className="flex aspect-[4/3] items-center justify-center overflow-hidden bg-white p-2">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={`/figures/${f.file}`}
                  alt={f.label}
                  loading="lazy"
                  className="max-h-full max-w-full object-contain"
                />
              </div>
              <div className="border-t border-border p-3">
                <p className="truncate text-sm font-medium text-ink" title={f.label}>
                  {f.label}
                </p>
                <p className="mt-0.5 truncate text-xs text-faint" title={f.src}>
                  {f.src}
                </p>
              </div>
            </button>
          ))}
        </div>
      )}

      {/* Lightbox */}
      {active && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
          onClick={() => setActive(null)}
          role="dialog"
          aria-modal="true"
          aria-label={active.label}
        >
          <div
            className="max-h-[90vh] max-w-4xl overflow-hidden rounded-lg border border-border bg-surface shadow-card"
            onClick={(e) => e.stopPropagation()}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={`/figures/${active.file}`}
              alt={active.label}
              className="max-h-[80vh] w-full bg-white object-contain"
            />
            <div className="flex items-center justify-between gap-3 border-t border-border bg-surface px-4 py-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-ink">{active.label}</p>
                <p className="truncate text-xs text-muted">{active.src}</p>
              </div>
              <button
                onClick={() => setActive(null)}
                className="shrink-0 rounded-lg border border-border px-3 py-1.5 text-sm font-medium text-muted hover:bg-elevated hover:text-ink"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function FilterChip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors ${
        active
          ? "border-accent bg-accent text-white"
          : "border-border bg-surface text-muted hover:bg-elevated hover:text-ink"
      }`}
    >
      {children}
    </button>
  );
}
