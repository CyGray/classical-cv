// Typed access to the generated manifest (ui/dashboard/data/manifest.json). Imported
// directly because it lives inside the Root Directory, so no fs call is needed and it
// is resolved at build time (DESIGN.md §6.5 monorepo fix).
import manifestJson from "@/data/manifest.json";

export type LegStatus = "done" | "in_progress" | "open" | "superseded";
export type PaperState =
  | "stale"
  | "partial"
  | "rewrite_needed"
  | "data_ready"
  | "current";

export interface Leg {
  model: string;
  dataset: string;
  test_type: string;
  artifact_path: string;
  run_date: string;
  status: LegStatus;
  protocol_note?: string;
  result_note?: string;
  superseded_by?: string | null;
  // derived
  artifact_exists: boolean;
  artifact_mtime: string;
  artifact_files: string[];
  artifact_size_bytes: number;
  slug: string;
}

export interface PaperSection {
  section: string;
  state: PaperState;
  needed: string;
}

export interface HeadlineFinding {
  active?: boolean;
  title?: string;
  summary?: string;
  source_doc?: string;
}

export interface Checklist {
  done?: string[];
  todo_paper?: string[];
  todo_open?: string[];
  out_of_scope?: string[];
}

export interface BenchmarkSummary {
  artifact: string;
  tracked_in_git: boolean;
  headline: Record<string, unknown>;
  run_date: string | null;
}

export interface Figure {
  src: string;
  file: string;
  label: string;
  group: string;
}

export interface Manifest {
  generated_at: string;
  source_yml_hash: string;
  study_status: {
    updated?: string;
    updated_by?: string;
    headline_finding: HeadlineFinding;
  };
  legs: Leg[];
  checklist: Checklist;
  paper_sections: PaperSection[];
  benchmark_summary: BenchmarkSummary[];
  figures: Figure[];
}

export const manifest = manifestJson as unknown as Manifest;

export function getLegBySlug(slug: string): Leg | undefined {
  return manifest.legs.find((l) => l.slug === slug);
}

export const TEST_TYPE_LABELS: Record<string, string> = {
  independence: "Independence",
  independence_light_front: "Independence (light front)",
  joint_independence: "Joint independence",
  "41mod_ar": "41-mod accuracy ratio",
  evidence_matrix: "Evidence matrix",
  tar_far: "TAR @ FAR",
  other: "Other",
};

export function testTypeLabel(t: string): string {
  return TEST_TYPE_LABELS[t] ?? t;
}
