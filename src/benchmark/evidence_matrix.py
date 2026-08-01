"""Evidence matrix: one frozen threshold set, every dataset, one table.

The generalization claim ("the hybrid works regardless of dataset") is only
defensible if the thresholds are derived ONCE and then applied everywhere
without re-tuning. Re-deriving thresholds per dataset shows the method is
*tunable*, which every method is - not that it *transfers*.

This harness therefore:

1. anchors on ``src/hybrid/thresholds.json`` (derived on La Salle DB1) and
   records its SHA-256, so the report proves every leg saw the same numbers;
2. runs each configured leg as a subprocess of the existing scripts:
   * ``independence`` legs -> ``src.hybrid.independence_test`` (N x (N-1)
     impostor sweep: FAR + error overlap + diversity statistics),
   * ``accuracy_ratio`` legs -> ``src.benchmark.accuracy_ratio_hybrid``
     (41-modification AR: cv_only / dl_only / cascade / parallel);
3. skips legs whose dataset directory does not exist (clearly marked SKIPPED,
   never silently dropped);
4. aggregates every leg's JSON into ``reports/benchmark/evidence_matrix.{json,md}``.

Default legs map to the four project datasets:

    ls_db1        independence   data/lasalle_db1_processed
    ls_db2_41mods accuracy_ratio data/split_lasalle/test  (41 mods generated
                                 deterministically in-process, seed 42)
    lfw1          independence   data/lfw-dataset
    lfw2_41mods   independence   data/lfw2_41mods  (pre-modified probes,
                                 one picture per identity)

Every dataset path is overridable; use ``--only`` / ``--skip`` to control the
run set and ``--dry-run`` to print the exact commands without executing.

Protocol invariants the report states explicitly: the gallery / enrollment
side is always clean originals - only probes are ever modified - and no
threshold is re-derived on any leg.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_THRESHOLDS = PROJECT_ROOT / "src" / "hybrid" / "thresholds.json"
OUT_JSON = PROJECT_ROOT / "outputs" / "benchmark" / "evidence_matrix.json"
OUT_MD = PROJECT_ROOT / "reports" / "benchmark" / "evidence_matrix.md"


@dataclass
class Leg:
    name: str
    kind: str                      # "independence" | "accuracy_ratio"
    dataset_dir: str               # identity folders (independence) / originals (AR)
    role: str                      # one line: what this leg proves
    iterations: int = 10           # independence only
    max_identities: int = 0        # independence only; 0 = all
    extra_args: list[str] = field(default_factory=list)

    def output_json(self) -> Path:
        if self.kind == "independence":
            return PROJECT_ROOT / "outputs" / "hybrid" / "independence_test" / self.name / "summary.json"
        return PROJECT_ROOT / "outputs" / "benchmark" / "evidence" / f"{self.name}.json"

    def command(self, thresholds: Path) -> list[str]:
        if self.kind == "independence":
            cmd = [
                sys.executable, "-m", "src.hybrid.independence_test",
                "--dataset-dir", self.dataset_dir,
                "--output-dir", str(self.output_json().parent),
                "--thresholds-json", str(thresholds),
                "--iterations", str(self.iterations),
            ]
            if self.max_identities:
                cmd += ["--max-identities", str(self.max_identities)]
        elif self.kind == "accuracy_ratio":
            out = self.output_json()
            cmd = [
                sys.executable, "-m", "src.benchmark.accuracy_ratio_hybrid",
                "--originals-dir", self.dataset_dir,
                "--thresholds-json", str(thresholds),
                "--output-json", str(out),
                "--output-md", str(out.with_suffix(".md")),
            ]
        else:
            raise ValueError(f"Unknown leg kind {self.kind!r}")
        return cmd + self.extra_args


def default_legs(args: argparse.Namespace) -> list[Leg]:
    return [
        Leg("ls_db1", "independence", args.ls_db1_dir,
            role="in-domain FAR anchor (thresholds were derived here)",
            iterations=args.iterations),
        Leg("ls_db2_41mods", "accuracy_ratio", args.ls_db2_dir,
            role="robustness under the 41 modifications, per-engine + cascade + parallel"),
        Leg("lfw1", "independence", args.lfw1_dir,
            role="out-of-domain transfer with real statistical power",
            iterations=args.lfw_iterations, max_identities=args.lfw_max_identities),
        Leg("lfw2_41mods", "independence", args.lfw2_dir,
            role="degradation x identity separation jointly, out-of-domain",
            iterations=args.lfw_iterations, max_identities=args.lfw_max_identities),
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run every dataset leg against ONE frozen thresholds.json and "
                    "aggregate the evidence matrix."
    )
    parser.add_argument("--thresholds-json", default=str(DEFAULT_THRESHOLDS),
                        help="The frozen (LS-DB1-derived) threshold set every leg uses.")
    parser.add_argument("--ls-db1-dir", default="data/lasalle_db1_processed")
    parser.add_argument("--ls-db2-dir", default="data/split_lasalle/test",
                        help="Clean originals; the 41 modifications are generated "
                             "deterministically in-process (seed 42).")
    parser.add_argument("--lfw1-dir", default="data/lfw-dataset")
    parser.add_argument("--lfw2-dir", default="data/lfw2_41mods",
                        help="Pre-modified LFW probes, one picture per identity.")
    parser.add_argument("--iterations", type=int, default=10,
                        help="Independence iterations on La Salle legs.")
    parser.add_argument("--lfw-iterations", type=int, default=3,
                        help="Independence iterations on LFW legs (heavier sweeps).")
    parser.add_argument("--lfw-max-identities", type=int, default=0,
                        help="Seeded identity subsample for the LFW legs (0 = all "
                             "5,749; a few hundred already beats La Salle's power).")
    parser.add_argument("--only", default="",
                        help="Comma list of leg names to run (default: all).")
    parser.add_argument("--skip", default="", help="Comma list of leg names to skip.")
    parser.add_argument("--reuse-existing", action="store_true",
                        help="Do not re-run a leg whose output JSON already exists; "
                             "just aggregate it.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the exact commands and exit without running.")
    parser.add_argument("--output-json", default=str(OUT_JSON))
    parser.add_argument("--output-md", default=str(OUT_MD))
    return parser.parse_args()


def _abs(path_value: str) -> Path:
    p = Path(path_value)
    return p if p.is_absolute() else PROJECT_ROOT / p


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_leg(leg: Leg, thresholds: Path, reuse: bool, dry_run: bool) -> dict:
    """Run one leg (or reuse/skip it) and return its status row."""
    dataset = _abs(leg.dataset_dir)
    row: dict = {
        "name": leg.name, "kind": leg.kind, "role": leg.role,
        "dataset_dir": str(dataset), "report": str(leg.output_json()),
    }
    if not dataset.is_dir():
        row["status"] = "SKIPPED (dataset directory not found)"
        return row
    cmd = leg.command(thresholds)
    row["command"] = " ".join(cmd)
    if dry_run:
        row["status"] = "DRY-RUN"
        return row
    if reuse and leg.output_json().exists():
        row["status"] = "REUSED existing report"
        return row
    print(f"\n{'=' * 70}\n[LEG {leg.name}] {leg.role}\n  $ {row['command']}\n{'=' * 70}")
    t0 = time.time()
    proc = subprocess.run(cmd, cwd=PROJECT_ROOT)
    row["elapsed_s"] = round(time.time() - t0, 1)
    row["status"] = "OK" if proc.returncode == 0 else f"FAILED (exit {proc.returncode})"
    return row


# --------------------------------------------------------------------------- #
# Aggregation
# --------------------------------------------------------------------------- #
def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def summarize_independence(payload: dict) -> dict:
    pooled = payload.get("pooled", {})
    rates = pooled.get("fp_rates_ci95", {})
    div = pooled.get("diversity", {})
    fisher = div.get("fisher", {})
    return {
        "identities": payload.get("dataset", {}).get("identities"),
        "iterations": payload.get("iterations"),
        "comparisons_per_iteration": payload.get("comparisons_per_iteration"),
        "pooled_comparisons": pooled.get("comparisons"),
        "far_ci95_percent": {k: rates.get(k) for k in ("lbph", "sface", "cascade")},
        "observed_over_expected_joint_fp": div.get("observed_over_expected"),
        "q_statistic": div.get("q_statistic"),
        "double_fault_percent": (
            100.0 * div["double_fault"] if div.get("double_fault") is not None else None
        ),
        "fisher_p_positive": fisher.get("p_positive"),
        "fisher_p_two_sided": fisher.get("p_two_sided"),
        "mean_escalation_percent": payload.get("mean_escalation_percent"),
    }


def summarize_accuracy_ratio(payload: dict) -> dict:
    comp = payload.get("complementarity", {})
    return {
        "originals": payload.get("originals"),
        "probes_per_mode": payload.get("modified_probes_per_mode"),
        "overall_ar_percent": payload.get("overall_ar_percent"),
        "overall_ar_pooled_ci95": payload.get("overall_ar_pooled_ci95"),
        "mean_latency_ms": payload.get("mean_latency_ms"),
        "cv_stronger": comp.get("cv_stronger"),
        "dl_stronger": comp.get("dl_stronger"),
        "cascade_vs_parallel": comp.get("cascade_vs_parallel"),
    }


def _fmt_ci(entry: dict | None) -> str:
    if not isinstance(entry, dict):
        return "n/a"
    return (f"{entry['percent']:.4f}% "
            f"[{entry['ci95_low_percent']:.4f}-{entry['ci95_high_percent']:.4f}]")


def _fmt(v, spec: str = ".3f") -> str:
    return format(v, spec) if isinstance(v, (int, float)) else "n/a"


def to_markdown(matrix: dict) -> str:
    lines = [
        "# Evidence matrix - one frozen threshold set, every dataset",
        "",
        f"Thresholds: `{matrix['thresholds_json']}` "
        f"(sha256 `{matrix['thresholds_sha256'][:16]}...`), derived on LS-DB1 and "
        "**never re-tuned** on any leg. Gallery/enrollment is always clean "
        "originals; only probes are modified.",
        "",
        "## Legs",
        "",
        "| Leg | Kind | Dataset | Proves | Status |",
        "|---|---|---|---|---|",
    ]
    for row in matrix["legs"]:
        lines.append(
            f"| {row['name']} | {row['kind']} | `{row['dataset_dir']}` | "
            f"{row['role']} | {row['status']} |"
        )
    lines.append("")

    ind = [r for r in matrix["legs"] if r["kind"] == "independence" and "summary" in r]
    if ind:
        lines += [
            "## Independence sweeps (impostor-only, pooled over iterations)",
            "",
            "| Leg | IDs | Comparisons | LBPH FAR [CI] | SFace FAR [CI] | "
            "Cascade FAR [CI] | Joint FP obs/exp | Yule Q | Fisher p(co-occur) |",
            "|---|---:|---:|---|---|---|---:|---:|---:|",
        ]
        for r in ind:
            s = r["summary"]
            far = s["far_ci95_percent"]
            lines.append(
                f"| {r['name']} | {s['identities']} | {s['pooled_comparisons']} | "
                f"{_fmt_ci(far['lbph'])} | {_fmt_ci(far['sface'])} | "
                f"{_fmt_ci(far['cascade'])} | "
                f"{_fmt(s['observed_over_expected_joint_fp'], '.2f')} | "
                f"{_fmt(s['q_statistic'])} | {_fmt(s['fisher_p_positive'], '.4g')} |"
            )
        lines.append("")

    ar = [r for r in matrix["legs"] if r["kind"] == "accuracy_ratio" and "summary" in r]
    if ar:
        lines += [
            "## 41-modification Accuracy Ratio",
            "",
            "| Leg | Probes/mode | cv_only | dl_only | cascade | parallel | "
            "cascade vs parallel |",
            "|---|---:|---|---|---|---|---|",
        ]
        for r in ar:
            s = r["summary"]
            ci = s.get("overall_ar_pooled_ci95") or {}
            cvp = s.get("cascade_vs_parallel") or {}
            cvp_cell = (
                f"{cvp['overall_points']:+.2f} pts, "
                f"{cvp['within_tolerance_mods']}/{cvp['total_mods']} mods in tolerance"
                if cvp else "n/a"
            )
            lines.append(
                f"| {r['name']} | {s['probes_per_mode']} | "
                + " | ".join(_fmt_ci(ci.get(m)) for m in
                             ("cv_only", "dl_only", "cascade", "parallel"))
                + f" | {cvp_cell} |"
            )
        lines.append("")

    lines += [
        "## Reading the matrix",
        "",
        "- **FAR transfer**: cascade FAR intervals overlapping across legs = the "
        "frozen thresholds generalize; a blow-up on LFW legs = thresholds are "
        "population-dependent (report it either way).",
        "- **Complementarity**: Yule Q < 0 (or obs/exp < 1) with a small Fisher "
        "p(avoid) means the engines fail on different pairs; the double-fault "
        "rate is the error floor of any fusion.",
        "- **Cascade vs parallel**: the cascade must stay within tolerance of the "
        "run-both ceiling while escalating only a fraction of probes - that is "
        "the efficiency claim.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    thresholds = _abs(args.thresholds_json)
    if not thresholds.exists():
        print(f"[ERROR] Frozen thresholds not found: {thresholds}")
        return 1

    only = {s.strip() for s in args.only.split(",") if s.strip()}
    skip = {s.strip() for s in args.skip.split(",") if s.strip()}
    legs = [
        leg for leg in default_legs(args)
        if (not only or leg.name in only) and leg.name not in skip
    ]

    matrix: dict = {
        "thresholds_json": str(thresholds),
        "thresholds_sha256": sha256_of(thresholds),
        "protocol": {
            "frozen_thresholds": "derived on LS-DB1; identical bytes on every leg",
            "gallery": "always clean originals; only probes are modified",
        },
        "legs": [],
    }
    for leg in legs:
        row = run_leg(leg, thresholds, args.reuse_existing, args.dry_run)
        if row["status"].startswith(("OK", "REUSED")):
            payload = _read_json(leg.output_json())
            if payload is None:
                row["status"] += " (report JSON unreadable)"
            elif leg.kind == "independence":
                row["summary"] = summarize_independence(payload)
            else:
                row["summary"] = summarize_accuracy_ratio(payload)
        matrix["legs"].append(row)

    if args.dry_run:
        for row in matrix["legs"]:
            print(f"[{row['status']}] {row['name']}: {row.get('command', row['status'])}")
        return 0

    out_json = _abs(args.output_json)
    out_md = _abs(args.output_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(matrix, indent=2), encoding="utf-8")
    out_md.write_text(to_markdown(matrix), encoding="utf-8")

    print(f"\n[OK] Evidence matrix: {out_json}")
    print(f"[OK] Evidence matrix: {out_md}")
    for row in matrix["legs"]:
        print(f"  {row['name']:<16} {row['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
