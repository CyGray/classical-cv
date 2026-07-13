import type { LegStatus, PaperState } from "@/lib/manifest";

const LEG_STYLES: Record<LegStatus, { label: string; cls: string; dot: string }> = {
  done: {
    label: "Done",
    cls: "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-300 dark:border-emerald-500/30",
    dot: "bg-emerald-500",
  },
  in_progress: {
    label: "In progress",
    cls: "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-500/10 dark:text-amber-300 dark:border-amber-500/30",
    dot: "bg-amber-500",
  },
  open: {
    label: "Open",
    cls: "bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-500/10 dark:text-rose-300 dark:border-rose-500/30",
    dot: "bg-rose-500",
  },
  superseded: {
    label: "Superseded",
    cls: "bg-slate-100 text-slate-500 border-slate-200 line-through dark:bg-slate-500/10 dark:text-slate-400 dark:border-slate-500/30",
    dot: "bg-slate-400",
  },
};

export function StatusBadge({ status }: { status: LegStatus }) {
  const s = LEG_STYLES[status] ?? LEG_STYLES.open;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${s.cls}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${s.dot}`} aria-hidden />
      {s.label}
    </span>
  );
}

const PAPER_STYLES: Record<PaperState, { label: string; cls: string }> = {
  current: {
    label: "Current",
    cls: "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-300 dark:border-emerald-500/30",
  },
  data_ready: {
    label: "Data ready",
    cls: "bg-sky-50 text-sky-700 border-sky-200 dark:bg-sky-500/10 dark:text-sky-300 dark:border-sky-500/30",
  },
  partial: {
    label: "Partial",
    cls: "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-500/10 dark:text-amber-300 dark:border-amber-500/30",
  },
  stale: {
    label: "Stale",
    cls: "bg-orange-50 text-orange-700 border-orange-200 dark:bg-orange-500/10 dark:text-orange-300 dark:border-orange-500/30",
  },
  rewrite_needed: {
    label: "Rewrite needed",
    cls: "bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-500/10 dark:text-rose-300 dark:border-rose-500/30",
  },
};

export function PaperStateBadge({ state }: { state: PaperState }) {
  const s = PAPER_STYLES[state] ?? PAPER_STYLES.partial;
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${s.cls}`}
    >
      {s.label}
    </span>
  );
}
