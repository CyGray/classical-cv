// Docs loader. The slug map is authoritative and mirrors DOC_SOURCES in
// scripts/utils/build_study_manifest.py. The disk path's "READ THIS" space is normalized
// to "read-this/" during the Phase-0 copy, so here we only ever touch clean slugs
// under content/docs/<slug>.md. URL segments never derive from a raw filename
// (DESIGN.md §6.2 hazard).
import fs from "node:fs";
import path from "node:path";

export interface DocEntry {
  slug: string;
  title: string;
  group: string;
}

// Kept in the SAME order/grouping as build_study_manifest.py's DOC_SOURCES.
export const DOC_ENTRIES: DocEntry[] = [
  { slug: "paper", title: "Paper (draft)", group: "Paper" },
  { slug: "recommendation", title: "Recommendation (Yule's Q verdict)", group: "Top-level" },
  { slug: "dl-error", title: "DL-track error", group: "Top-level" },
  { slug: "read-this/briefing", title: "Briefing", group: "Read this first" },
  { slug: "read-this/classical-track-audit", title: "Classical Track Audit", group: "Read this first" },
  { slug: "read-this/instructions", title: "Instructions", group: "Read this first" },
  { slug: "read-this/cfp-2026", title: "IW-FCV 2026 Call for Papers", group: "Read this first" },
  { slug: "reports/architecture", title: "Architecture Report", group: "Reports" },
  { slug: "reports/classical-improvement", title: "Classical Improvement Research", group: "Reports" },
  { slug: "reports/dataset-matrix", title: "Dataset Matrix", group: "Reports" },
  { slug: "reports/detector-comparison", title: "Detector Comparison", group: "Reports" },
  { slug: "reports/hybrid-cv-dl", title: "Hybrid CV/DL Report", group: "Reports" },
  { slug: "reports/spec-comparison", title: "Spec Comparison", group: "Reports" },
  { slug: "audits/state-07-10", title: "Research State Audit (2026-07-10)", group: "Audits" },
  { slug: "audits/improvement-spec", title: "Improvement Spec", group: "Audits" },
  { slug: "audits/2026-07-08-improvement", title: "Improvement Spec Implementation (07-08)", group: "Audits" },
  { slug: "audits/2026-07-09-dl-gap", title: "DL-track Detection Gap (07-09)", group: "Audits" },
  { slug: "changelogs/changelog", title: "Changelog", group: "Changelogs" },
  { slug: "changelogs/0407", title: "Changelog 04-07", group: "Changelogs" },
  { slug: "changelogs/0421", title: "Changelog 04-21", group: "Changelogs" },
  { slug: "presentation/complementarity-battery", title: "Complementarity Battery: Why & How", group: "Presentation" },
  { slug: "presentation/independence-expansion", title: "Independence Test Expansion: Why & How", group: "Presentation" },
];

const CONTENT_ROOT = path.join(process.cwd(), "content", "docs");

export function getAllDocSlugs(): string[] {
  return DOC_ENTRIES.map((d) => d.slug);
}

export function getDocEntry(slug: string): DocEntry | undefined {
  return DOC_ENTRIES.find((d) => d.slug === slug);
}

export function getDocBySlug(slug: string): { entry: DocEntry; content: string } | null {
  const entry = getDocEntry(slug);
  if (!entry) return null;
  const file = path.join(CONTENT_ROOT, `${slug}.md`);
  if (!fs.existsSync(file)) return null;
  return { entry, content: fs.readFileSync(file, "utf-8") };
}

export function docsByGroup(): { group: string; docs: DocEntry[] }[] {
  const order: string[] = [];
  const map = new Map<string, DocEntry[]>();
  for (const d of DOC_ENTRIES) {
    if (!map.has(d.group)) {
      map.set(d.group, []);
      order.push(d.group);
    }
    map.get(d.group)!.push(d);
  }
  return order.map((group) => ({ group, docs: map.get(group)! }));
}
