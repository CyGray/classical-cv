"use client";

import Link from "next/link";
import { useState } from "react";
import { manifest, testTypeLabel } from "@/lib/manifest";
import { StatusBadge, PaperStateBadge } from "./StatusBadge";

const TABS = [
  { id: "legs", label: "Per-leg runs" },
  { id: "checklist", label: "Master checklist" },
  { id: "paper", label: "Paper coverage" },
] as const;
type TabId = (typeof TABS)[number]["id"];

export function StatusView() {
  const [tab, setTab] = useState<TabId>("legs");

  return (
    <div>
      <div role="tablist" aria-label="Study status views" className="mb-6 flex flex-wrap gap-1 border-b border-border">
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={tab === t.id}
            onClick={() => setTab(t.id)}
            className={`border-b-2 px-3 py-2 text-sm font-medium transition-colors ${
              tab === t.id
                ? "border-accent text-ink"
                : "border-transparent text-muted hover:text-ink"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "legs" && <LegsTable />}
      {tab === "checklist" && <ChecklistView />}
      {tab === "paper" && <PaperTable />}
    </div>
  );
}

function LegsTable() {
  const legs = manifest.legs;
  return (
    <div className="overflow-hidden rounded-lg border border-border bg-surface">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-elevated text-left font-mono text-xs uppercase tracking-wide text-muted">
              <th className="px-4 py-2.5 font-medium">Model</th>
              <th className="px-4 py-2.5 font-medium">Dataset / leg</th>
              <th className="px-4 py-2.5 font-medium">Test</th>
              <th className="px-4 py-2.5 font-medium">Run date</th>
              <th className="px-4 py-2.5 font-medium">Status</th>
              <th className="px-4 py-2.5 font-medium" />
            </tr>
          </thead>
          <tbody>
            {legs.map((leg) => (
              <tr
                key={leg.slug}
                className="border-b border-border/60 last:border-0 hover:bg-elevated/40"
              >
                <td className="whitespace-nowrap px-4 py-2.5 font-medium text-ink">
                  {leg.model}
                </td>
                <td className="px-4 py-2.5 text-ink">{leg.dataset}</td>
                <td className="whitespace-nowrap px-4 py-2.5 text-muted">
                  {testTypeLabel(leg.test_type)}
                </td>
                <td className="whitespace-nowrap px-4 py-2.5 font-mono text-muted">
                  {leg.run_date}
                </td>
                <td className="px-4 py-2.5">
                  <StatusBadge status={leg.status} />
                </td>
                <td className="whitespace-nowrap px-4 py-2.5 text-right">
                  <Link
                    href={`/status/legs/${leg.slug}`}
                    className="text-sm font-medium text-accent hover:underline"
                  >
                    Details →
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ChecklistColumn({
  title,
  items,
  tone,
  strike = false,
}: {
  title: string;
  items?: string[];
  tone: string;
  strike?: boolean;
}) {
  return (
    <div className="rounded-lg border border-border bg-surface p-5">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="font-semibold text-ink">{title}</h3>
        <span className={`font-mono text-xs font-medium ${tone}`}>
          {items?.length ?? 0}
        </span>
      </div>
      <ul className="space-y-2">
        {(items ?? []).map((item, i) => (
          <li key={i} className="flex gap-2 text-sm text-muted">
            <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-current opacity-50" aria-hidden />
            <span className={strike ? "line-through" : ""}>{item}</span>
          </li>
        ))}
        {(!items || items.length === 0) && (
          <li className="text-sm text-faint">Nothing here.</li>
        )}
      </ul>
    </div>
  );
}

function ChecklistView() {
  const c = manifest.checklist;
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <ChecklistColumn title="Done" items={c.done} tone="text-emerald-600 dark:text-emerald-400" />
      <ChecklistColumn title="Paper to-do (writing only)" items={c.todo_paper} tone="text-sky-600 dark:text-sky-400" />
      <ChecklistColumn title="Open to-do (needs a run)" items={c.todo_open} tone="text-rose-600 dark:text-rose-400" />
      <ChecklistColumn title="Out of scope (Paper 2)" items={c.out_of_scope} tone="text-faint" strike />
    </div>
  );
}

function PaperTable() {
  const sections = manifest.paper_sections;
  return (
    <div className="space-y-3">
      {sections.map((s, i) => (
        <div
          key={i}
          className="rounded-lg border border-border bg-surface p-4 sm:flex sm:items-start sm:gap-4"
        >
          <div className="mb-2 flex items-center gap-3 sm:mb-0 sm:w-64 sm:shrink-0">
            <PaperStateBadge state={s.state} />
            <span className="font-medium text-ink">{s.section}</span>
          </div>
          <p className="text-sm leading-relaxed text-muted">{s.needed}</p>
        </div>
      ))}
    </div>
  );
}
