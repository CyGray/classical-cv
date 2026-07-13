import type { LegStatus, PaperState } from "@/lib/manifest";
import type { ResultVerdict } from "@/lib/results";

// Dot + plain ink text, no filled pill: color still encodes status, it just stops
// being decoration. Same mechanism reused by PaperStateBadge and VerdictBadge below.
function Dot({ children, dot }: { children: React.ReactNode; dot: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-ink">
      <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${dot}`} aria-hidden />
      {children}
    </span>
  );
}

const LEG_STYLES: Record<LegStatus, { label: string; dot: string; strike?: boolean }> = {
  done: { label: "Done", dot: "bg-emerald-500" },
  in_progress: { label: "In progress", dot: "bg-amber-500" },
  open: { label: "Open", dot: "bg-rose-500" },
  superseded: { label: "Superseded", dot: "bg-faint", strike: true },
};

export function StatusBadge({ status }: { status: LegStatus }) {
  const s = LEG_STYLES[status] ?? LEG_STYLES.open;
  return (
    <Dot dot={s.dot}>
      <span className={s.strike ? "text-muted line-through" : undefined}>{s.label}</span>
    </Dot>
  );
}

const PAPER_STYLES: Record<PaperState, { label: string; dot: string }> = {
  current: { label: "Current", dot: "bg-emerald-500" },
  data_ready: { label: "Data ready", dot: "bg-sky-500" },
  partial: { label: "Partial", dot: "bg-amber-500" },
  stale: { label: "Stale", dot: "bg-orange-500" },
  rewrite_needed: { label: "Rewrite needed", dot: "bg-rose-500" },
};

export function PaperStateBadge({ state }: { state: PaperState }) {
  const s = PAPER_STYLES[state] ?? PAPER_STYLES.partial;
  return <Dot dot={s.dot}>{s.label}</Dot>;
}

const VERDICT_STYLES: Record<ResultVerdict, { label: string; dot: string }> = {
  confirms: { label: "Confirms", dot: "bg-emerald-500" },
  refutes: { label: "Refutes", dot: "bg-rose-500" },
  mixed: { label: "Mixed", dot: "bg-amber-500" },
  caveat: { label: "Caveat", dot: "bg-orange-500" },
  methodology: { label: "Methodology", dot: "bg-faint" },
};

export function VerdictBadge({ verdict }: { verdict: ResultVerdict }) {
  const s = VERDICT_STYLES[verdict] ?? VERDICT_STYLES.methodology;
  return <Dot dot={s.dot}>{s.label}</Dot>;
}
