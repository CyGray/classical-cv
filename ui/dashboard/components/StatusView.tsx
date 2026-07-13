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
      <div role="tablist" aria-label="Study status views" className="mb-6 flex flex-wrap gap-1 rounded-xl border border-border bg-surface p-1 shadow-card">
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={tab === t.id}
            onClick={() => setTab(t.id)}
            className={`flex-1 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
              tab === t.id
                ? "bg-brand text-white shadow-sm"
                : "text-muted hover:bg-elevated hover:text-ink"
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
    <div className="overflow-hidden rounded-xl border border-border bg-surface shadow-card">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-elevated text-left text-xs uppercase tracking-wide text-muted">
              <th className="px-4 py-3 font-semibold">Model</th>
              <th className="px-4 py-3 font-semibold">Dataset / leg</th>
              <th className="px-4 py-3 font-semibold">Test</th>
              <th className="px-4 py-3 font-semibold">Run date</th>
              <th className="px-4 py-3 font-semibold">Status</th>
              <th className="px-4 py-3 font-semibold" />
            </tr>
          </thead>
          <tbody>
            {legs.map((leg) => (
              <tr
                key={leg.slug}
                className="border-b border-border/60 last:border-0 hover:bg-elevated/40"
              >
                <td className="whitespace-nowrap px-4 py-3 font-medium text-ink">
                  {leg.model}
                </td>
                <td className="px-4 py-3 text-ink">{leg.dataset}</td>
                <td className="whitespace-nowrap px-4 py-3 text-muted">
                  {testTypeLabel(leg.test_type)}
                </td>
                <td className="whitespace-nowrap px-4 py-3 text-muted">
                  {leg.run_date}
                </td>
                <td className="px-4 py-3">
                  <StatusBadge status={leg.status} />
                </td>
                <td className="whitespace-nowrap px-4 py-3 text-right">
                  <Link
                    href={`/status/legs/${leg.slug}`}
                    className="text-sm font-medium text-brand hover:underline"
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
    <div className="rounded-xl border border-border bg-surface p-5 shadow-card">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="font-semibold text-ink">{title}</h3>
        <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${tone}`}>
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
      <ChecklistColumn title="Done" items={c.done} tone="bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300" />
      <ChecklistColumn title="Paper to-do (writing only)" items={c.todo_paper} tone="bg-sky-100 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300" />
      <ChecklistColumn title="Open to-do (needs a run)" items={c.todo_open} tone="bg-rose-100 text-rose-700 dark:bg-rose-500/15 dark:text-rose-300" />
      <ChecklistColumn title="Out of scope (Paper 2)" items={c.out_of_scope} tone="bg-slate-100 text-slate-500 dark:bg-slate-500/15 dark:text-slate-400" strike />
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
          className="rounded-xl border border-border bg-surface p-4 shadow-card sm:flex sm:items-start sm:gap-4"
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
