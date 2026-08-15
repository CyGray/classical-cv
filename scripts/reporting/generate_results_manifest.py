"""Write per-artifact provenance/status metadata for docs/results."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "docs" / "results"
MANIFEST = RESULTS / "RESULTS_MANIFEST.json"
CANONICAL_DESCRIPTIVE_CAMPAIGNS = {
    "complementarity_test/reruns/gate_accept_protection_descriptive_2026-08-13/": (
        "Post-hoc same-data known-genuine routing replay; cite only with its "
        "recorded descriptive limitations."
    ),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rerun_provenance(path: Path) -> dict | None:
    """Load a rerun's recorded inputs when the artifact has one."""
    for parent in (path.parent, *path.parents):
        candidate = parent / "run_provenance.json"
        if candidate.is_file():
            provenance = json.loads(candidate.read_text(encoding="utf-8"))
            # A documented rerun may live in any result category, not only
            # independence_test/reruns.  Keep its canonical directory in-memory
            # so source_path() can recover the matching raw-artifact suffix.
            if "source_output_dir" in provenance:
                provenance["_results_run_dir"] = parent.relative_to(RESULTS).as_posix()
                return provenance
        if parent == RESULTS:
            break
    return None


def source_path(rel: str, provenance: dict | None = None) -> str:
    if provenance and rel.endswith("run_provenance.json"):
        return "docs/results/" + rel
    if provenance:
        run_dir = Path(provenance["_results_run_dir"])
        rerun_artifact = Path(rel).relative_to(run_dir).as_posix()
        canonical_derivatives = set(provenance.get("canonical_only_artifacts", []))
        canonical_derivatives.update(provenance.get("canonicalized_artifacts", {}))
        if rerun_artifact in canonical_derivatives:
            return "docs/results/" + rel
        raw_path = ROOT / provenance["source_output_dir"] / rerun_artifact
        if raw_path.is_file():
            return f"{provenance['source_output_dir']}/{rerun_artifact}"
        # Method notes added while promoting a raw rerun are canonical-only
        # documentation, not files that existed in its source output.
        return "docs/results/" + rel
    if rel.startswith("independence_test/independence/"):
        return "classical-cv/reports/independence/" + rel.split("/independence/", 1)[1]
    if rel.startswith("robustness_test/benchmark/"):
        return "classical-cv/reports/benchmark/" + rel.split("/benchmark/", 1)[1]
    if rel.startswith("algo_test/preprocess/"):
        return "classical-cv/reports/preprocess/" + rel.split("/preprocess/", 1)[1]
    if rel.startswith("algo_test/lfw_all_families/"):
        return "classical-cv/reports/benchmark/lfw_all_families/" + rel.rsplit("/", 1)[-1]
    direct = {
        "algo_test/fig1_tar_far_roc.png": "classical-cv/reports/figures/fig1_tar_far_roc.png",
        "algo_test/fig4_latency_fps.png": "classical-cv/reports/figures/fig4_latency_fps.png",
        "independence_test/fig2_interidentity_hist.png": "classical-cv/reports/figures/fig2_interidentity_hist.png",
        "robustness_test/fig3_ar_by_modification.png": "classical-cv/reports/figures/fig3_ar_by_modification.png",
        "robustness_test/standins/hybrid_robustness_tables.png": "classical-cv/reports/figures/hybrid_robustness_tables.png",
        "robustness_test/lfw2_standalone_full_table.png": "classical-cv/reports/lfw2_standalone_full_table.png",
        "robustness_test/lfw2_standalone_tier_summary.png": "classical-cv/reports/lfw2_standalone_tier_summary.png",
    }
    if rel in direct:
        return direct[rel]
    if rel.startswith("robustness_test/") and rel.endswith(".png"):
        return "classical-cv/reports/figures/" + rel.rsplit("/", 1)[-1]
    return "docs/results/" + rel


def git_last_change(path: str) -> tuple[str | None, str | None]:
    result = subprocess.run(
        ["git", "log", "-1", "--format=%H%x00%aI", "--", path],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    value = result.stdout.strip()
    return tuple(value.split("\x00", 1)) if "\x00" in value else (None, None)


def classification(rel: str, provenance: dict | None = None) -> tuple[str, bool, str | None]:
    for prefix, reason in CANONICAL_DESCRIPTIVE_CAMPAIGNS.items():
        if rel.startswith(prefix):
            if provenance is None:
                return (
                    "needs_provenance_review",
                    False,
                    "Descriptive campaign artifact lacks run_provenance.json.",
                )
            if provenance.get("status") != "canonical_descriptive_only":
                return (
                    "needs_provenance_review",
                    False,
                    "Descriptive campaign provenance status does not match its allowlist.",
                )
            return "canonical_descriptive_only", False, reason
    if rel.startswith("independence_test/reruns/"):
        if provenance:
            return "canonical_snapshot", False, None
        return "needs_provenance_review", False, "Rerun artifact lacks run_provenance.json."
    if rel == "robustness_test/41mods_table/table.png":
        return "reference_specification", False, "Reference table; not an experimental result."
    if rel.startswith("algo_test/preprocess/step"):
        return "illustrative_stand_in", False, "Preprocessing illustration; not a headline measurement."
    if rel.startswith("robustness_test/standins/"):
        return "illustrative_stand_in", False, "Presentation stand-in; do not cite as a canonical result."
    if rel.startswith("independence_test/independence/hybrid/lfw1"):
        return "rerun_required", True, "Full-frame LBPH harness artifact; invalid for deployed box-cropped comparison."
    if rel in {
        "algo_test/fig1_tar_far_roc.png",
        "independence_test/fig2_interidentity_hist.png",
        "robustness_test/fig3_ar_by_modification.png",
    }:
        return "historical_rerun_required", True, "Embedded manuscript raster; historical operating point or incomplete run provenance."
    if rel.startswith("robustness_test/benchmark/lfw2_cropfix_subset/"):
        return "needs_provenance_review", False, "Arm/configuration provenance must be confirmed before citation."
    if rel.endswith(".png"):
        return "needs_provenance_review", False, "Raster artifact has no per-file run metadata; verify source before citation."
    return "canonical_snapshot", False, None


def source_script(rel: str, provenance: dict | None = None) -> str:
    if provenance:
        run_dir = Path(provenance["_results_run_dir"])
        rerun_artifact = Path(rel).relative_to(run_dir).as_posix()
        canonical_derivatives = set(provenance.get("canonical_only_artifacts", []))
        canonical_derivatives.update(provenance.get("canonicalized_artifacts", {}))
        if rerun_artifact in canonical_derivatives:
            return "not recorded"
        if not rel.endswith("run_provenance.json"):
            if not (ROOT / provenance["source_output_dir"] / rerun_artifact).is_file():
                return "not recorded"
        return provenance["source_script"]
    if rel.endswith("native_predict_scale_yunet.json"):
        return "classical-cv/scripts/archive/run_lfw_lbph_native_predict_independence.py"
    if rel.endswith("standalone_l2_yunet.json"):
        return "classical-cv/scripts/archive/run_lfw_sface_standalone_independence.py"
    if "far_sweep" in rel:
        return "classical-cv/scripts/far_sweep_impostor_thresholds.py"
    if "tau_reject_tradeoff" in rel:
        return "classical-cv/scripts/pipeline/tau_reject_tradeoff_curve.py"
    if "accuracy_ratio_hybrid" in rel:
        return "classical-cv/scripts/pipeline/run_lfw2_robustness.py"
    if "/independence/" in rel and rel.endswith(".png"):
        return "classical-cv/src/independence_report.py"
    return "not recorded"


def main() -> None:
    artifacts = []
    for path in sorted(RESULTS.rglob("*")):
        if not path.is_file() or path == MANIFEST:
            continue
        rel = path.relative_to(RESULTS).as_posix()
        provenance = rerun_provenance(path)
        status, rerun_required, reason = classification(rel, provenance)
        origin = source_path(rel, provenance)
        if provenance:
            commit = provenance.get("source_git_commit")
            committed_at = provenance.get("source_git_commit_at")
        else:
            commit, committed_at = git_last_change(origin)
        artifacts.append(
            {
                "path": rel,
                "source_path": origin,
                "source_script": source_script(rel, provenance),
                "artifact_type": path.suffix.lstrip(".").lower() or "file",
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
                "last_commit": commit,
                "last_commit_at": committed_at,
                "status": status,
                "rerun_required": rerun_required,
                "status_reason": reason,
            }
        )
    assert artifacts, "docs/results contains no artifacts"
    MANIFEST.write_text(
        json.dumps(
            {
                "schema": "lsface-results-manifest-v1",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "artifact_count": len(artifacts),
                "artifacts": artifacts,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"[OK] {len(artifacts)} artifacts -> {MANIFEST}")


if __name__ == "__main__":
    main()
