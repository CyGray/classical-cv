#!/usr/bin/env python3
"""Build the Researcher Dashboard's data manifest from the hand-maintained study status.

Pipeline (docs/ui/DESIGN.md §7):

    docs/ui/study_status.yml  ->  scripts/build_study_manifest.py  ->
        ui/dashboard/data/manifest.json          (generated, committed)
        ui/dashboard/content/docs/**             (copied .md, §6.5 monorepo fix)
        ui/dashboard/content/results/**          (copied summary.json)
        ui/dashboard/public/figures/**           (copied .png)

The yml is the ONLY source of judgment calls (status / paper state / headline). This
script ADDS mechanical facts it derives by scanning reports/ (artifact_exists, mtime,
size, file listing) and copies the files the dashboard renders into its own Root
Directory so Vercel never needs to read outside ui/dashboard/.

# Vercel Root Directory sandboxes builds ("cannot use `..`"); the content/ and
# public/figures/ copy-step below makes ui/dashboard/ self-contained, so it is
# load-bearing regardless of whether the "include files outside Root Directory"
# checkbox exists (DESIGN.md §6.5 / BUILD.md 0.3). Do not remove it.

The .gitignore decision (BUILD.md 0.1c) is "summarize-only": reports/benchmark/** and
reports/evaluation/** stay ignored; this script reads the locally-present-but-gitignored
benchmark JSON and copies only the headline numbers into manifest.benchmark_summary[].
Never the raw file.

Run:  python scripts/build_study_manifest.py
Exits non-zero (loudly) if any legs[].artifact_path in the yml does not exist on disk.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import shutil
import sys
from pathlib import Path

import yaml

# --- Paths --------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
STATUS_YML = REPO_ROOT / "docs" / "ui" / "study_status.yml"
DASHBOARD = REPO_ROOT / "ui" / "dashboard"
MANIFEST_PATH = DASHBOARD / "data" / "manifest.json"
CONTENT_DOCS = DASHBOARD / "content" / "docs"
CONTENT_RESULTS = DASHBOARD / "content" / "results"
PUBLIC_FIGURES = DASHBOARD / "public" / "figures"

# --- Explicit doc source map (DESIGN.md §6.2) ---------------------------------
# The disk path (may contain a space, read via Python — never shell-globbed) is never
# exposed in a URL; the slug (no space, explicit) is what the App Router uses. The
# copy step normalizes "READ THIS" -> "read-this" so lib/docs.ts never special-cases
# a space (BUILD.md 1.2 recommendation).
DOC_SOURCES: list[dict[str, str]] = [
    # slug, diskPath (repo-relative), title, group
    {"slug": "paper", "disk": "docs/PAPER.md", "title": "Paper (draft)", "group": "Paper"},
    {"slug": "recommendation", "disk": "docs/RECOMMENDATION.md", "title": "Recommendation (Yule's Q verdict)", "group": "Top-level"},
    {"slug": "dl-error", "disk": "docs/DL_ERROR.md", "title": "DL-track error", "group": "Top-level"},
    # READ THIS/
    {"slug": "read-this/briefing", "disk": "docs/READ THIS/BRIEFING.md", "title": "Briefing", "group": "Read this first"},
    {"slug": "read-this/classical-track-audit", "disk": "docs/READ THIS/CLASSICAL_TRACK_AUDIT.md", "title": "Classical Track Audit", "group": "Read this first"},
    {"slug": "read-this/instructions", "disk": "docs/READ THIS/INSTRUCTIONS.md", "title": "Instructions", "group": "Read this first"},
    {"slug": "read-this/cfp-2026", "disk": "docs/READ THIS/IW-FCV_2026_Call_for_Papers.md", "title": "IW-FCV 2026 Call for Papers", "group": "Read this first"},
    # reports/
    {"slug": "reports/architecture", "disk": "docs/reports/ARCHITECTURE_REPORT.md", "title": "Architecture Report", "group": "Reports"},
    {"slug": "reports/classical-improvement", "disk": "docs/reports/CLASSICAL_IMPROVEMENT_RESEARCH.md", "title": "Classical Improvement Research", "group": "Reports"},
    {"slug": "reports/dataset-matrix", "disk": "docs/reports/DATASET_MATRIX.md", "title": "Dataset Matrix", "group": "Reports"},
    {"slug": "reports/detector-comparison", "disk": "docs/reports/DETECTOR_COMPARISON.md", "title": "Detector Comparison", "group": "Reports"},
    {"slug": "reports/hybrid-cv-dl", "disk": "docs/reports/HYBRID_CV_DL_REPORT.md", "title": "Hybrid CV/DL Report", "group": "Reports"},
    {"slug": "reports/spec-comparison", "disk": "docs/reports/SPEC_COMPARISON.md", "title": "Spec Comparison", "group": "Reports"},
    # audits/
    {"slug": "audits/state-07-10", "disk": "docs/audits/STATE-07-10.md", "title": "Research State Audit (2026-07-10)", "group": "Audits"},
    {"slug": "audits/improvement-spec", "disk": "docs/audits/IMPROVEMENT_SPEC.md", "title": "Improvement Spec", "group": "Audits"},
    {"slug": "audits/2026-07-08-improvement", "disk": "docs/audits/2026-07-08_improvement_spec_implementation.md", "title": "Improvement Spec Implementation (07-08)", "group": "Audits"},
    {"slug": "audits/2026-07-09-dl-gap", "disk": "docs/audits/2026-07-09_dl_track_detection_gap.md", "title": "DL-track Detection Gap (07-09)", "group": "Audits"},
    # changelogs/
    {"slug": "changelogs/changelog", "disk": "docs/changelogs/CHANGELOG.md", "title": "Changelog", "group": "Changelogs"},
    {"slug": "changelogs/0407", "disk": "docs/changelogs/0407.md", "title": "Changelog 04-07", "group": "Changelogs"},
    {"slug": "changelogs/0421", "disk": "docs/changelogs/0421.md", "title": "Changelog 04-21", "group": "Changelogs"},
    # presentation/
    {"slug": "presentation/complementarity-battery", "disk": "docs/presentation/complementarity_battery/WHY_AND_HOW.md", "title": "Complementarity Battery — Why & How", "group": "Presentation"},
    {"slug": "presentation/independence-expansion", "disk": "docs/presentation/independence_test_expansion/WHY_AND_HOW.md", "title": "Independence Test Expansion — Why & How", "group": "Presentation"},
]

# Figure sources (DESIGN.md §6.3). Each dir is enumerated; every .png copied flat
# into public/figures/ under a namespaced filename so galleries never collide.
FIGURE_DIRS: list[tuple[str, str]] = [
    ("docs/figures", "docs"),
    ("reports/figures", "reports"),
    ("docs/presentation/complementarity_battery", "battery"),
    ("docs/presentation/independence_test_expansion", "independence"),
]

# Benchmark JSONs to summarize (gitignored-but-local; summarize-only per §7).
BENCHMARK_SOURCES = [
    "reports/benchmark/accuracy_ratio_hybrid.json",
    "reports/benchmark/gate_operating_curve.json",
    "reports/benchmark/evidence_matrix.json",
]


# --- Helpers ------------------------------------------------------------------
def _iso(ts: float) -> str:
    return _dt.datetime.fromtimestamp(ts, _dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fatal(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def _scan_artifact(rel: str) -> dict:
    """Mechanical facts about a legs[].artifact_path. Hard-fails if it does not exist."""
    p = (REPO_ROOT / rel).resolve()
    if not p.exists():
        _fatal(
            f"artifact_path does not exist: {rel}\n"
            f"       (resolved: {p})\n"
            f"       Fix study_status.yml — do not loosen this check (DESIGN.md §7.1)."
        )
    if p.is_file():
        st = p.stat()
        return {
            "artifact_exists": True,
            "artifact_mtime": _iso(st.st_mtime),
            "artifact_files": [p.name],
            "artifact_size_bytes": st.st_size,
        }
    files = sorted(f for f in p.iterdir() if f.is_file())
    all_files = [f for f in p.rglob("*") if f.is_file()]
    newest = max((f.stat().st_mtime for f in all_files), default=p.stat().st_mtime)
    total = sum(f.stat().st_size for f in all_files)
    return {
        "artifact_exists": True,
        "artifact_mtime": _iso(newest),
        "artifact_files": [f.name for f in files],
        "artifact_size_bytes": total,
    }


def _summarize_benchmarks() -> list[dict]:
    """Read gitignored-but-local benchmark JSON; copy only headline numbers (§7.2)."""
    out: list[dict] = []
    for rel in BENCHMARK_SOURCES:
        p = REPO_ROOT / rel
        if not p.exists():
            print(f"  (skip benchmark, not present locally: {rel})")
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        headline: dict = {}
        if "overall_ar_percent" in data:
            headline["overall_ar_percent"] = {
                k: round(v, 2) for k, v in data["overall_ar_percent"].items()
            }
        if "mean_latency_ms" in data:
            headline["mean_latency_ms"] = {
                k: round(v, 2) for k, v in data["mean_latency_ms"].items()
            }
        if "deployed" in data:  # gate_operating_curve.json
            d = data["deployed"]
            headline["deployed_gate"] = {
                k: (round(v, 2) if isinstance(v, (int, float)) else v)
                for k, v in d.items()
            }
        if "thresholds_sha256" in data:  # evidence_matrix.json
            headline["thresholds_sha256"] = data["thresholds_sha256"]
            headline["legs"] = [
                leg.get("leg") or leg.get("name") for leg in data.get("legs", [])
            ]
        out.append(
            {
                "artifact": rel,
                "tracked_in_git": False,
                "headline": headline,
                "run_date": None,
            }
        )
    return out


def _copy_docs() -> int:
    n = 0
    for src in DOC_SOURCES:
        disk = REPO_ROOT / src["disk"]
        if not disk.exists():
            _fatal(f"DOC_SOURCES path missing: {src['disk']}")
        dest = CONTENT_DOCS / f"{src['slug']}.md"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(disk, dest)
        n += 1
    return n


def _copy_figures() -> list[dict]:
    figures: list[dict] = []
    for rel_dir, ns in FIGURE_DIRS:
        d = REPO_ROOT / rel_dir
        if not d.exists():
            continue
        for png in sorted(d.glob("*.png")):
            name = f"{ns}__{png.name}"
            shutil.copy2(png, PUBLIC_FIGURES / name)
            figures.append(
                {
                    "src": f"{rel_dir}/{png.name}",
                    "file": name,  # under ui/dashboard/public/figures/
                    "label": png.stem,
                    "group": ns,
                }
            )
    return figures


def _copy_results() -> int:
    """Copy top-level per-leg summary.json (skip _raw_runs/) into content/results/**."""
    n = 0
    root = REPO_ROOT / "reports" / "independence"
    for summ in root.rglob("summary.json"):
        if "_raw_runs" in summ.parts:
            continue
        rel = summ.relative_to(root)
        dest = CONTENT_RESULTS / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(summ, dest)
        n += 1
    return n


def _slugify_leg(leg: dict) -> str:
    raw = f"{leg['model']}-{leg['dataset']}-{leg['test_type']}".lower()
    out = []
    prev_dash = False
    for ch in raw:
        if ch.isalnum():
            out.append(ch)
            prev_dash = False
        elif not prev_dash:
            out.append("-")
            prev_dash = True
    return "".join(out).strip("-")


def _reset_generated_dirs() -> None:
    """Clear copied trees so removed sources don't linger as stale committed files."""
    for d in (CONTENT_DOCS, CONTENT_RESULTS, PUBLIC_FIGURES):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True, exist_ok=True)


# --- Main ---------------------------------------------------------------------
def main() -> None:
    if not STATUS_YML.exists():
        _fatal(f"missing {STATUS_YML.relative_to(REPO_ROOT)} (write it first — BUILD.md 0.5)")

    raw_text = STATUS_YML.read_text(encoding="utf-8")
    status = yaml.safe_load(raw_text)
    yml_hash = "sha256:" + hashlib.sha256(raw_text.encode("utf-8")).hexdigest()

    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    _reset_generated_dirs()

    # legs[]: yml fields verbatim + derived mechanical facts + a stable slug.
    legs_out = []
    seen_slugs: dict[str, int] = {}
    for leg in status.get("legs", []):
        derived = _scan_artifact(leg["artifact_path"])
        slug = _slugify_leg(leg)
        if slug in seen_slugs:
            seen_slugs[slug] += 1
            slug = f"{slug}-{seen_slugs[slug]}"
        else:
            seen_slugs[slug] = 1
        legs_out.append({**leg, **derived, "slug": slug})

    figures = _copy_figures()
    n_docs = _copy_docs()
    n_results = _copy_results()

    manifest = {
        "generated_at": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_yml_hash": yml_hash,
        "study_status": {
            "updated": status.get("updated"),
            "updated_by": status.get("updated_by"),
            "headline_finding": status.get("headline_finding", {}),
        },
        "legs": legs_out,
        "checklist": status.get("checklist", {}),
        "paper_sections": status.get("paper_sections", []),
        "benchmark_summary": _summarize_benchmarks(),
        "figures": figures,
    }

    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    size_kb = MANIFEST_PATH.stat().st_size / 1024
    print("Study manifest built:")
    print(f"  manifest       : {MANIFEST_PATH.relative_to(REPO_ROOT)}  ({size_kb:.1f} KB)")
    print(f"  legs           : {len(legs_out)}  (all artifact_exists=True)")
    print(f"  docs copied    : {n_docs}  -> {CONTENT_DOCS.relative_to(REPO_ROOT)}")
    print(f"  figures copied : {len(figures)}  -> {PUBLIC_FIGURES.relative_to(REPO_ROOT)}")
    print(f"  results copied : {n_results}  -> {CONTENT_RESULTS.relative_to(REPO_ROOT)}")
    print(f"  benchmarks     : {len(manifest['benchmark_summary'])} summarized")


if __name__ == "__main__":
    main()
