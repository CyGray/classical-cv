#!/usr/bin/env python3
"""Post-hoc smoke test for LBPH-to-SFace gate ordering variants.

This script does not rescore images or alter the deployed gate. It replays
candidate routing policies over the canonical LSDB-DL41 per-probe score table
and writes explicitly experimental artifacts beside this file.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import random
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


SCRIPT_PATH = Path(__file__).resolve()
WORKSPACE_ROOT = SCRIPT_PATH.parents[4]

DEFAULT_RECORDS = (
    WORKSPACE_ROOT
    / "docs/results/complementarity_test/reruns/lsdb_dl41_2026-08-10/"
    "gate_operating_curve_probes.csv"
)
DEFAULT_REFERENCE = DEFAULT_RECORDS.with_name("gate_operating_curve.json")
DEFAULT_THRESHOLDS = WORKSPACE_ROOT / "classical-cv/src/hybrid/thresholds.json"

QUALITY_COLUMNS = {
    "blur": "flag_blur",
    "low_light": "flag_low_light",
    "noise": "flag_noise",
    "off_pose": "flag_off_pose",
    "small_face": "flag_small_face",
}
ALL_QUALITY_FLAGS = frozenset(QUALITY_COLUMNS)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replay experimental gate policies over stored LSDB-DL41 scores."
    )
    parser.add_argument("--records", type=Path, default=DEFAULT_RECORDS)
    parser.add_argument("--thresholds", type=Path, default=DEFAULT_THRESHOLDS)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--output-dir", type=Path, default=SCRIPT_PATH.parent)
    parser.add_argument("--bootstrap-replicates", type=int, default=20_000)
    parser.add_argument("--bootstrap-seed", type=int, default=20260813)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def as_bool(value: str | None) -> bool:
    return str(value).strip().lower() == "true"


def as_float(value: str | None) -> float | None:
    if value is None or not str(value).strip():
        return None
    return float(value)


@dataclass(frozen=True)
class Probe:
    row_index: int
    person: str
    mod: str
    level: str
    no_face: bool
    lbph_name: str
    d1: float | None
    margin: float | None
    lbph_correct: bool
    sface_name: str
    sface_thresholded_correct: bool
    quality_flags: frozenset[str]
    lbph_ms: float
    sface_ms: float


@dataclass(frozen=True)
class Policy:
    name: str
    description: str
    quality_flags: frozenset[str]
    quality_overrides_accept: bool
    quality_overrides_reject: bool
    margin_accept_min: float | None
    margin_reject_min: float | None


@dataclass(frozen=True)
class Decision:
    action: str  # no_face | accept_lbph | escalate_sface | reject_unknown
    reason: str

    @property
    def escalated(self) -> bool:
        return self.action == "escalate_sface"


@dataclass(frozen=True)
class Outcome:
    probe: Probe
    decision: Decision
    correct: bool
    latency_ms: float


def load_probes(path: Path) -> tuple[list[Probe], dict]:
    probes: list[Probe] = []
    stored_column_mismatches = 0
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {
            "person",
            "mod",
            "level",
            "lbph_name",
            "d1",
            "margin",
            "sface_name",
            "lbph_ms",
            "sface_ms",
            *QUALITY_COLUMNS.values(),
        }
        missing = sorted(required - set(reader.fieldnames or ()))
        if missing:
            raise ValueError(f"Missing required CSV columns: {missing}")

        for row_index, row in enumerate(reader, start=2):
            d1 = as_float(row.get("d1"))
            margin = as_float(row.get("margin"))
            no_face = d1 is None
            person = row["person"]
            lbph_name = row.get("lbph_name", "")
            sface_name = row.get("sface_name", "")
            lbph_correct = (not no_face) and lbph_name == person
            sface_correct = (not no_face) and sface_name == person
            stored_sface = row.get("sface_rank1_correct")
            if stored_sface and as_bool(stored_sface) != sface_correct:
                stored_column_mismatches += 1
            active_flags = frozenset(
                name for name, column in QUALITY_COLUMNS.items() if as_bool(row.get(column))
            )
            probes.append(
                Probe(
                    row_index=row_index,
                    person=person,
                    mod=row["mod"],
                    level=row.get("level", ""),
                    no_face=no_face,
                    lbph_name=lbph_name,
                    d1=d1,
                    margin=margin,
                    lbph_correct=lbph_correct,
                    sface_name=sface_name,
                    sface_thresholded_correct=sface_correct,
                    quality_flags=active_flags,
                    lbph_ms=float(row.get("lbph_ms") or 0.0),
                    sface_ms=float(row.get("sface_ms") or 0.0),
                )
            )
    return probes, {"stored_sface_correct_column_mismatches": stored_column_mismatches}


def route(probe: Probe, policy: Policy, *, tau_accept: float, tau_reject: float) -> Decision:
    if probe.no_face:
        return Decision("no_face", "no_face")
    assert probe.d1 is not None and probe.margin is not None
    active_quality = sorted(probe.quality_flags & policy.quality_flags)

    if probe.d1 <= tau_accept:
        if policy.quality_overrides_accept and active_quality:
            return Decision("escalate_sface", "quality:" + ",".join(active_quality))
        if policy.margin_accept_min is not None and probe.margin < policy.margin_accept_min:
            return Decision("escalate_sface", "low_margin_accept")
        return Decision("accept_lbph", "confident_accept")

    if probe.d1 < tau_reject:
        if active_quality:
            return Decision("escalate_sface", "quality:" + ",".join(active_quality))
        return Decision("escalate_sface", "ambiguous_band")

    if policy.quality_overrides_reject and active_quality:
        return Decision("escalate_sface", "quality:" + ",".join(active_quality))
    if policy.margin_reject_min is not None and probe.margin < policy.margin_reject_min:
        return Decision("escalate_sface", "low_margin_reject")
    return Decision("reject_unknown", "confident_reject")


def apply_policy(
    probes: Iterable[Probe], policy: Policy, *, tau_accept: float, tau_reject: float
) -> list[Outcome]:
    outcomes: list[Outcome] = []
    for probe in probes:
        decision = route(probe, policy, tau_accept=tau_accept, tau_reject=tau_reject)
        if decision.action == "escalate_sface":
            correct = probe.sface_thresholded_correct
            latency_ms = probe.lbph_ms + probe.sface_ms
        elif decision.action == "accept_lbph":
            correct = probe.lbph_correct
            latency_ms = probe.lbph_ms
        elif decision.action == "reject_unknown":
            correct = False
            latency_ms = probe.lbph_ms
        else:
            correct = False
            latency_ms = 0.0
        outcomes.append(Outcome(probe, decision, correct, latency_ms))
    return outcomes


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return ordered[lo]
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


def macro_ar(modified: list[Outcome]) -> float:
    per_mod_level: dict[str, dict[str, list[int]]] = defaultdict(
        lambda: defaultdict(lambda: [0, 0])
    )
    for outcome in modified:
        slot = per_mod_level[outcome.probe.mod][outcome.probe.level]
        slot[0] += int(outcome.correct)
        slot[1] += 1
    mod_scores = []
    for levels in per_mod_level.values():
        level_scores = [100.0 * matched / total for matched, total in levels.values()]
        mod_scores.append(sum(level_scores) / len(level_scores))
    return sum(mod_scores) / len(mod_scores)


def summarize(outcomes: list[Outcome], *, tau_accept: float) -> dict:
    modified = [outcome for outcome in outcomes if outcome.probe.mod != "clean"]
    clean = [outcome for outcome in outcomes if outcome.probe.mod == "clean"]
    scored_modified = [outcome for outcome in modified if not outcome.probe.no_face]
    strict_correct = [
        outcome
        for outcome in scored_modified
        if outcome.probe.d1 is not None
        and outcome.probe.d1 <= tau_accept
        and outcome.probe.lbph_correct
    ]
    strict_wrong = [
        outcome
        for outcome in scored_modified
        if outcome.probe.d1 is not None
        and outcome.probe.d1 <= tau_accept
        and not outcome.probe.lbph_correct
    ]
    raw_rank1_correct = [outcome for outcome in scored_modified if outcome.probe.lbph_correct]
    raw_rank1_correct_escalated = [
        outcome for outcome in raw_rank1_correct if outcome.decision.escalated
    ]
    latencies = [outcome.latency_ms for outcome in modified]
    escalated_modified = [outcome for outcome in modified if outcome.decision.escalated]
    return {
        "modified_rows": len(modified),
        "modified_scored_rows": len(scored_modified),
        "modified_no_face_rows": sum(outcome.probe.no_face for outcome in modified),
        "overall_ar_percent": macro_ar(modified),
        "pooled_correct_count": sum(outcome.correct for outcome in modified),
        "pooled_accuracy_percent": 100.0 * sum(outcome.correct for outcome in modified) / len(modified),
        "escalation_count": len(escalated_modified),
        "escalation_percent": 100.0 * len(escalated_modified) / len(modified),
        "mean_latency_ms": sum(latencies) / len(latencies),
        "latency_p50_ms": percentile(latencies, 0.50),
        "latency_p95_ms": percentile(latencies, 0.95),
        "clean_rows": len(clean),
        "clean_correct_count": sum(outcome.correct for outcome in clean),
        "clean_accuracy_percent": 100.0 * sum(outcome.correct for outcome in clean) / len(clean),
        "clean_escalation_count": sum(outcome.decision.escalated for outcome in clean),
        "clean_escalation_percent": 100.0
        * sum(outcome.decision.escalated for outcome in clean)
        / len(clean),
        "strict_lbph_accept_correct_count": len(strict_correct),
        "strict_lbph_accept_correct_escalated_count": sum(
            outcome.decision.escalated for outcome in strict_correct
        ),
        "strict_lbph_accept_wrong_count": len(strict_wrong),
        "strict_lbph_accept_wrong_rescued_count": sum(
            outcome.decision.escalated and outcome.correct for outcome in strict_wrong
        ),
        "raw_lbph_rank1_correct_count": len(raw_rank1_correct),
        "raw_lbph_rank1_correct_escalated_count": len(raw_rank1_correct_escalated),
        "raw_lbph_rank1_correct_escalated_to_sface_failure_count": sum(
            not outcome.correct for outcome in raw_rank1_correct_escalated
        ),
        "decision_reason_counts_modified": dict(
            sorted(Counter(outcome.decision.reason for outcome in modified).items())
        ),
    }


def compare(candidate: list[Outcome], deployed: list[Outcome], summaries: dict) -> dict:
    saved = [
        (base, cand)
        for base, cand in zip(deployed, candidate)
        if base.decision.escalated and not cand.decision.escalated
    ]
    added = [
        (base, cand)
        for base, cand in zip(deployed, candidate)
        if not base.decision.escalated and cand.decision.escalated
    ]
    gains = [
        (base, cand)
        for base, cand in zip(deployed, candidate)
        if not base.correct and cand.correct
    ]
    losses = [
        (base, cand)
        for base, cand in zip(deployed, candidate)
        if base.correct and not cand.correct
    ]
    saved_modified = [pair for pair in saved if pair[0].probe.mod != "clean"]
    saved_clean = [pair for pair in saved if pair[0].probe.mod == "clean"]
    added_modified = [pair for pair in added if pair[0].probe.mod != "clean"]
    added_clean = [pair for pair in added if pair[0].probe.mod == "clean"]
    gains_modified = [pair for pair in gains if pair[0].probe.mod != "clean"]
    gains_clean = [pair for pair in gains if pair[0].probe.mod == "clean"]
    losses_modified = [pair for pair in losses if pair[0].probe.mod != "clean"]
    losses_clean = [pair for pair in losses if pair[0].probe.mod == "clean"]
    base_summary = summaries["deployed"]
    candidate_summary = summarize(candidate, tau_accept=summaries["_tau_accept"])
    return {
        "delta_overall_ar_points": candidate_summary["overall_ar_percent"]
        - base_summary["overall_ar_percent"],
        "delta_pooled_accuracy_points": candidate_summary["pooled_accuracy_percent"]
        - base_summary["pooled_accuracy_percent"],
        "delta_escalation_points": candidate_summary["escalation_percent"]
        - base_summary["escalation_percent"],
        "delta_mean_latency_ms": candidate_summary["mean_latency_ms"]
        - base_summary["mean_latency_ms"],
        "saved_sface_calls_all_count": len(saved),
        "saved_sface_calls_modified_count": len(saved_modified),
        "saved_sface_calls_clean_count": len(saved_clean),
        "added_sface_calls_all_count": len(added),
        "added_sface_calls_modified_count": len(added_modified),
        "added_sface_calls_clean_count": len(added_clean),
        "correctness_gains_all_count": len(gains),
        "correctness_gains_modified_count": len(gains_modified),
        "correctness_gains_clean_count": len(gains_clean),
        "correctness_losses_all_count": len(losses),
        "correctness_losses_modified_count": len(losses_modified),
        "correctness_losses_clean_count": len(losses_clean),
        "saved_calls_on_strict_lbph_correct_count": sum(
            base.probe.mod != "clean"
            and base.probe.d1 is not None
            and base.probe.d1 <= summaries["_tau_accept"]
            and base.probe.lbph_correct
            for base, _ in saved
        ),
    }


def direct_anchor(probes: list[Probe], kind: str, *, tau_accept: float) -> dict:
    modified = [probe for probe in probes if probe.mod != "clean"]
    clean = [probe for probe in probes if probe.mod == "clean"]

    def correct(probe: Probe) -> bool:
        if probe.no_face:
            return False
        if kind == "lbph":
            return bool(probe.lbph_correct and probe.d1 is not None and probe.d1 <= tau_accept)
        return probe.sface_thresholded_correct

    def latency(probe: Probe) -> float:
        return probe.lbph_ms if kind == "lbph" else probe.sface_ms

    pseudo = [
        Outcome(
            probe,
            Decision("accept_lbph" if kind == "lbph" else "escalate_sface", f"direct_{kind}"),
            correct(probe),
            latency(probe),
        )
        for probe in probes
    ]
    pseudo_modified = [outcome for outcome in pseudo if outcome.probe.mod != "clean"]
    return {
        "overall_ar_percent": macro_ar(pseudo_modified),
        "pooled_accuracy_percent": 100.0 * sum(correct(probe) for probe in modified) / len(modified),
        "mean_latency_ms": sum(latency(probe) for probe in modified) / len(modified),
        "clean_accuracy_percent": 100.0 * sum(correct(probe) for probe in clean) / len(clean),
    }


def clustered_bootstrap_delta(
    deployed: list[Outcome],
    candidate: list[Outcome],
    *,
    replicates: int,
    seed: int,
) -> dict:
    by_person: dict[str, list[tuple[Outcome, Outcome]]] = defaultdict(list)
    for base, cand in zip(deployed, candidate):
        if base.probe.mod != "clean":
            by_person[base.probe.person].append((base, cand))
    people = sorted(by_person)
    rng = random.Random(seed)
    accuracy_deltas: list[float] = []
    escalation_deltas: list[float] = []
    latency_deltas: list[float] = []
    for _ in range(replicates):
        sampled = [rng.choice(people) for _ in people]
        pairs = [pair for person in sampled for pair in by_person[person]]
        n = len(pairs)
        accuracy_deltas.append(
            100.0 * sum(int(cand.correct) - int(base.correct) for base, cand in pairs) / n
        )
        escalation_deltas.append(
            100.0
            * sum(int(cand.decision.escalated) - int(base.decision.escalated) for base, cand in pairs)
            / n
        )
        latency_deltas.append(sum(cand.latency_ms - base.latency_ms for base, cand in pairs) / n)
    return {
        "unit": "identity cluster",
        "identities": len(people),
        "replicates": replicates,
        "seed": seed,
        "pooled_accuracy_delta_points_ci95": [
            percentile(accuracy_deltas, 0.025),
            percentile(accuracy_deltas, 0.975),
        ],
        "escalation_delta_points_ci95": [
            percentile(escalation_deltas, 0.025),
            percentile(escalation_deltas, 0.975),
        ],
        "mean_latency_delta_ms_ci95": [
            percentile(latency_deltas, 0.025),
            percentile(latency_deltas, 0.975),
        ],
        "warning": "Descriptive only: policies were examined on the same LSDB-DL41 rows.",
    }


def git_value(*args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=WORKSPACE_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def flat_policy_row(name: str, policy: Policy, summary: dict, delta: dict) -> dict:
    return {
        "policy": name,
        "description": policy.description,
        "overall_ar_percent": summary["overall_ar_percent"],
        "pooled_correct_count": summary["pooled_correct_count"],
        "escalation_count": summary["escalation_count"],
        "escalation_percent": summary["escalation_percent"],
        "mean_latency_ms": summary["mean_latency_ms"],
        "clean_accuracy_percent": summary["clean_accuracy_percent"],
        "clean_escalation_percent": summary["clean_escalation_percent"],
        "strict_lbph_correct_escalated": summary[
            "strict_lbph_accept_correct_escalated_count"
        ],
        "strict_lbph_wrong_rescued": summary["strict_lbph_accept_wrong_rescued_count"],
        "raw_lbph_rank1_correct_escalated": summary[
            "raw_lbph_rank1_correct_escalated_count"
        ],
        "raw_lbph_rank1_correct_escalated_to_sface_failure": summary[
            "raw_lbph_rank1_correct_escalated_to_sface_failure_count"
        ],
        **delta,
    }


def main() -> int:
    args = parse_args()
    records_path = args.records.resolve()
    thresholds_path = args.thresholds.resolve()
    reference_path = args.reference.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    thresholds_payload = json.loads(thresholds_path.read_text(encoding="utf-8"))
    gate = thresholds_payload["gate"]
    tau_accept = float(gate["tau_accept"])
    tau_reject = float(gate["tau_reject"])
    margin_min = float(gate["margin_min"])
    probes, load_checks = load_probes(records_path)

    policies = [
        Policy(
            "deployed",
            "Current order: any quality flag, band, margin, then accept/reject.",
            ALL_QUALITY_FLAGS,
            True,
            True,
            margin_min,
            margin_min,
        ),
        Policy(
            "quality_not_over_accept",
            "Quality flags cannot override d<=tau_accept; current margin veto remains.",
            ALL_QUALITY_FLAGS,
            False,
            True,
            margin_min,
            margin_min,
        ),
        Policy(
            "accept_margin_guard_0_025",
            "Recommended smoke candidate: quality cannot override strict accept; accept-side margin veto is 0.025; reject side stays deployed.",
            ALL_QUALITY_FLAGS,
            False,
            True,
            0.025,
            margin_min,
        ),
        Policy(
            "strict_accept_precedence",
            "Nothing overrides d<=tau_accept; quality and deployed margin can still rescue hard rejects.",
            ALL_QUALITY_FLAGS,
            False,
            True,
            None,
            margin_min,
        ),
        Policy(
            "no_quality",
            "Disable all quality triggers; keep deployed margin on accept and reject sides.",
            frozenset(),
            False,
            False,
            margin_min,
            margin_min,
        ),
        Policy(
            "no_margin",
            "Disable margin triggers; retain deployed quality overrides.",
            ALL_QUALITY_FLAGS,
            True,
            True,
            None,
            None,
        ),
        Policy(
            "band_only",
            "Escalate only inside tau_accept<d<tau_reject.",
            frozenset(),
            False,
            False,
            None,
            None,
        ),
    ]

    policy_outcomes = {
        policy.name: apply_policy(
            probes, policy, tau_accept=tau_accept, tau_reject=tau_reject
        )
        for policy in policies
    }
    summaries: dict[str, dict | float] = {"_tau_accept": tau_accept}
    for policy in policies:
        summaries[policy.name] = summarize(policy_outcomes[policy.name], tau_accept=tau_accept)
    deployed_outcomes = policy_outcomes["deployed"]

    comparisons = {
        policy.name: compare(policy_outcomes[policy.name], deployed_outcomes, summaries)
        for policy in policies
    }

    reference = json.loads(reference_path.read_text(encoding="utf-8"))["deployed"]
    reproduced = summaries["deployed"]
    assert isinstance(reproduced, dict)
    validation = {
        "rows_total": len(probes),
        "rows_clean": sum(probe.mod == "clean" for probe in probes),
        "rows_modified": sum(probe.mod != "clean" for probe in probes),
        "records_sha256": sha256(records_path),
        "thresholds_sha256": sha256(thresholds_path),
        **load_checks,
        "deployed_reference_differences": {
            "overall_ar_percent": reproduced["overall_ar_percent"]
            - float(reference["overall_ar_percent"]),
            "clean_acceptance_percent": reproduced["clean_accuracy_percent"]
            - float(reference["clean_acceptance_percent"]),
            "mean_latency_ms": reproduced["mean_latency_ms"]
            - float(reference["mean_latency_ms"]),
            "escalation_percent": reproduced["escalation_percent"]
            - float(reference["escalation_percent"]),
        },
    }
    if len(probes) != 2352 or validation["rows_clean"] != 56 or validation["rows_modified"] != 2296:
        raise AssertionError(f"Unexpected source row counts: {validation}")
    if load_checks["stored_sface_correct_column_mismatches"]:
        raise AssertionError("Stored SFace correctness column does not match thresholded sface_name.")
    if any(abs(value) > 1e-9 for value in validation["deployed_reference_differences"].values()):
        raise AssertionError(f"Failed to reproduce deployed reference: {validation}")

    policy_rows = [
        flat_policy_row(
            policy.name,
            policy,
            summaries[policy.name],
            comparisons[policy.name],
        )
        for policy in policies
    ]
    policy_fields = [
        "policy",
        "description",
        "overall_ar_percent",
        "pooled_correct_count",
        "escalation_count",
        "escalation_percent",
        "mean_latency_ms",
        "clean_accuracy_percent",
        "clean_escalation_percent",
        "strict_lbph_correct_escalated",
        "strict_lbph_wrong_rescued",
        "raw_lbph_rank1_correct_escalated",
        "raw_lbph_rank1_correct_escalated_to_sface_failure",
        "delta_overall_ar_points",
        "delta_pooled_accuracy_points",
        "delta_escalation_points",
        "delta_mean_latency_ms",
        "saved_sface_calls_all_count",
        "saved_sface_calls_modified_count",
        "saved_sface_calls_clean_count",
        "added_sface_calls_all_count",
        "added_sface_calls_modified_count",
        "added_sface_calls_clean_count",
        "correctness_gains_all_count",
        "correctness_gains_modified_count",
        "correctness_gains_clean_count",
        "correctness_losses_all_count",
        "correctness_losses_modified_count",
        "correctness_losses_clean_count",
        "saved_calls_on_strict_lbph_correct_count",
    ]
    write_csv(output_dir / "policy_summary.csv", policy_rows, policy_fields)

    quality_rows = []
    for flag in sorted(ALL_QUALITY_FLAGS):
        for ablation, enabled in (
            ("leave_one_out", ALL_QUALITY_FLAGS - {flag}),
            ("only_flag", frozenset({flag})),
        ):
            policy = Policy(
                f"quality_{ablation}_{flag}",
                f"Quality {ablation.replace('_', ' ')}: {flag}.",
                frozenset(enabled),
                True,
                True,
                margin_min,
                margin_min,
            )
            outcomes = apply_policy(probes, policy, tau_accept=tau_accept, tau_reject=tau_reject)
            summary = summarize(outcomes, tau_accept=tau_accept)
            delta = compare(outcomes, deployed_outcomes, summaries)
            quality_rows.append(
                {
                    "ablation": ablation,
                    "flag": flag,
                    "enabled_flags": ",".join(sorted(enabled)),
                    **flat_policy_row(policy.name, policy, summary, delta),
                }
            )
    write_csv(
        output_dir / "quality_flag_ablation.csv",
        quality_rows,
        ["ablation", "flag", "enabled_flags", *policy_fields],
    )

    margin_rows = []
    for accept_margin in (0.0, 0.025, 0.05, 0.1, 0.2):
        policy = Policy(
            f"accept_margin_guard_{accept_margin:g}",
            "Quality cannot override strict accept; accept-side margin swept; reject side deployed.",
            ALL_QUALITY_FLAGS,
            False,
            True,
            accept_margin if accept_margin > 0.0 else None,
            margin_min,
        )
        outcomes = apply_policy(probes, policy, tau_accept=tau_accept, tau_reject=tau_reject)
        summary = summarize(outcomes, tau_accept=tau_accept)
        delta = compare(outcomes, deployed_outcomes, summaries)
        margin_rows.append(
            {
                "accept_margin_min": accept_margin,
                **flat_policy_row(policy.name, policy, summary, delta),
            }
        )
    write_csv(
        output_dir / "accept_margin_sweep.csv",
        margin_rows,
        ["accept_margin_min", *policy_fields],
    )

    primary_name = "quality_not_over_accept"
    sensitivity_name = "accept_margin_guard_0_025"
    primary = policy_outcomes[primary_name]
    changed_rows = []
    for base, candidate in zip(deployed_outcomes, primary):
        if base.decision == candidate.decision:
            continue
        changed_rows.append(
            {
                "source_csv_line": base.probe.row_index,
                "person": base.probe.person,
                "mod": base.probe.mod,
                "level": base.probe.level,
                "d1": base.probe.d1,
                "margin": base.probe.margin,
                "quality_flags": ",".join(sorted(base.probe.quality_flags)),
                "lbph_rank1_correct": base.probe.lbph_correct,
                "sface_thresholded_correct": base.probe.sface_thresholded_correct,
                "deployed_action": base.decision.action,
                "deployed_reason": base.decision.reason,
                "candidate_action": candidate.decision.action,
                "candidate_reason": candidate.decision.reason,
                "deployed_correct": base.correct,
                "candidate_correct": candidate.correct,
                "lbph_ms": base.probe.lbph_ms,
                "sface_ms": base.probe.sface_ms,
            }
        )
    changed_fields = [
        "source_csv_line",
        "person",
        "mod",
        "level",
        "d1",
        "margin",
        "quality_flags",
        "lbph_rank1_correct",
        "sface_thresholded_correct",
        "deployed_action",
        "deployed_reason",
        "candidate_action",
        "candidate_reason",
        "deployed_correct",
        "candidate_correct",
        "lbph_ms",
        "sface_ms",
    ]
    write_csv(output_dir / "primary_candidate_changed_rows.csv", changed_rows, changed_fields)

    bootstrap = clustered_bootstrap_delta(
        deployed_outcomes,
        primary,
        replicates=args.bootstrap_replicates,
        seed=args.bootstrap_seed,
    )
    anchors = {
        "lbph_only_strict": direct_anchor(probes, "lbph", tau_accept=tau_accept),
        "sface_only_direct": direct_anchor(probes, "sface", tau_accept=tau_accept),
    }
    primary_summary = summaries[primary_name]
    assert isinstance(primary_summary, dict)
    sensitivity_summary = summaries[sensitivity_name]
    assert isinstance(sensitivity_summary, dict)
    primary_vs_sface = {
        "accuracy_delta_points": primary_summary["overall_ar_percent"]
        - anchors["sface_only_direct"]["overall_ar_percent"],
        "mean_latency_delta_ms": primary_summary["mean_latency_ms"]
        - anchors["sface_only_direct"]["mean_latency_ms"],
        "mean_latency_relative_percent": 100.0
        * (
            primary_summary["mean_latency_ms"]
            / anchors["sface_only_direct"]["mean_latency_ms"]
            - 1.0
        ),
    }

    results = {
        "status": "experimental_posthoc_smoke_not_canonical",
        "scope": "Stored LSDB held-out tiles under the DL41 transform-sensitivity battery; known genuine probes only.",
        "method": "Pure routing replay over stored engine scores and timings; no image/model re-inference.",
        "thresholds": {
            "tau_accept": tau_accept,
            "tau_reject": tau_reject,
            "margin_min": margin_min,
        },
        "validation": validation,
        "policies": {
            policy.name: {
                "definition": policy.description,
                "summary": summaries[policy.name],
                "versus_deployed": comparisons[policy.name],
            }
            for policy in policies
        },
        "primary_candidate": primary_name,
        "exploratory_sensitivity_candidate": sensitivity_name,
        "candidate_selection_note": (
            "The primary retains the deployed margin_min=0.05. The 0.025 sensitivity "
            "is not recommended from these rows because it separates one rescued LBPH error "
            "from the next accepted-correct margin post hoc."
        ),
        "primary_candidate_changed_rows": len(changed_rows),
        "primary_candidate_identity_cluster_bootstrap": bootstrap,
        "anchors": anchors,
        "primary_candidate_versus_direct_sface": primary_vs_sface,
        "limitations": [
            "Post-hoc and in-sample: the same 2,296 modified rows motivated and evaluated the policies.",
            "Known genuine probes only: no unknown-query FPIR/FMR or security conclusion is possible.",
            "The stored sface_name is thresholded; its correctness is not raw threshold-free SFace Rank-1.",
            "DL41 rows are correlated transforms of 56 source images from 28 identities.",
            "Latency is arithmetic replay of stored recognition-stage timings, excluding detector/I/O and target hardware.",
            "A locked identity/session-disjoint open-set rerun is required before changing gate.py or making a paper claim.",
        ],
    }
    results_path = output_dir / "results.json"
    results_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    deployed_summary = summaries["deployed"]
    assert isinstance(deployed_summary, dict)
    primary_delta = comparisons[primary_name]
    sensitivity_delta = comparisons[sensitivity_name]
    readme = f"""# Gate accept-protection smoke test (2026-08-13)

Status: **experimental post-hoc smoke test; not canonical and not for paper citation**.

This replay uses the stored LSDB-DL41 per-probe scores. It does not rescore
images, change `gate.py`, retune `tau_accept`, or measure unknown-query FPIR.

## Main result

| Policy | AR (%) | Escalation (%) | Mean stored-stage latency (ms) | Strict-correct LBPH accepts escalated |
|---|---:|---:|---:|---:|
| Deployed | {deployed_summary['overall_ar_percent']:.4f} | {deployed_summary['escalation_percent']:.4f} | {deployed_summary['mean_latency_ms']:.4f} | {deployed_summary['strict_lbph_accept_correct_escalated_count']} |
| Quality cannot override strict accept; margin 0.05 retained | {primary_summary['overall_ar_percent']:.4f} | {primary_summary['escalation_percent']:.4f} | {primary_summary['mean_latency_ms']:.4f} | {primary_summary['strict_lbph_accept_correct_escalated_count']} |
| Exploratory margin 0.025 sensitivity | {sensitivity_summary['overall_ar_percent']:.4f} | {sensitivity_summary['escalation_percent']:.4f} | {sensitivity_summary['mean_latency_ms']:.4f} | {sensitivity_summary['strict_lbph_accept_correct_escalated_count']} |
| Direct SFace anchor | {anchors['sface_only_direct']['overall_ar_percent']:.4f} | N/A | {anchors['sface_only_direct']['mean_latency_ms']:.4f} | N/A |

The conservative candidate prevents quality flags from overriding
`d <= tau_accept`, retains the deployed `margin_min=0.05` veto, and leaves
all behavior above `tau_accept` unchanged. On the 2,296 modified rows it saved
**{primary_delta['saved_sface_calls_modified_count']} SFace calls** (plus
{primary_delta['saved_sface_calls_clean_count']} clean calls), changed AR by
**{primary_delta['delta_overall_ar_points']:+.4f}**
points, cut escalation by **{-primary_delta['delta_escalation_points']:.4f}**
points, and cut the arithmetic mean by
**{-primary_delta['delta_mean_latency_ms']:.4f} ms**.

It still remained **{primary_vs_sface['mean_latency_delta_ms']:.4f} ms
({primary_vs_sface['mean_latency_relative_percent']:.1f}%) slower** than the
direct SFace anchor. This improves the current cascade but does not establish
an efficiency win over SFace.

## Margin sensitivity

The deployed gate escalated 289 modified probes that LBPH would correctly
accept at the frozen threshold. Removing every accept-side override also lost
one SFace rescue: a low-distance LBPH misidentification with margin 0.022716.
The already-used smoke-grid value 0.025 retained that rescue while avoiding
all 289 strict-correct escalations on this dataset. It saved
{sensitivity_delta['saved_sface_calls_modified_count']} modified SFace calls
and reached {sensitivity_summary['mean_latency_ms']:.4f} ms with unchanged AR.
That apparent one-row separator is post-hoc overfitting, so 0.025 is a
sensitivity result - not the recommended policy.

## Two meanings of "LBPH could get it right"

- **Actionable deployed definition:** Rank-1 identity correct and
  `d <= tau_accept`. The conservative candidate reduces escalations from
  {deployed_summary['strict_lbph_accept_correct_escalated_count']} to
  {primary_summary['strict_lbph_accept_correct_escalated_count']} of
  {primary_summary['strict_lbph_accept_correct_count']} such modified probes.
- **Raw oracle definition:** LBPH Rank-1 identity correct regardless of its
  threshold. The candidate still escalates
  {primary_summary['raw_lbph_rank1_correct_escalated_count']} of
  {primary_summary['raw_lbph_rank1_correct_count']} such probes, and
  {primary_summary['raw_lbph_rank1_correct_escalated_to_sface_failure_count']}
  end as thresholded SFace failures. Fixing those requires a newly calibrated
  accept/risk model under open-set FPIR, not just gate reordering.

## Files

- `results.json`: complete machine-readable results and caveats.
- `policy_summary.csv`: primary policy comparison.
- `accept_margin_sweep.csv`: accept-side margin smoke grid.
- `quality_flag_ablation.csv`: per-quality-flag leave-one-out and only-flag checks.
- `primary_candidate_changed_rows.csv`: auditable route changes.
- `run_provenance.json`: hashes, environment, command, and non-canonical status.
- `smoke_gate_policies.py`: replay implementation.

## Mandatory limitations

1. The policies were motivated and evaluated on the same 56 source images / 28 identities.
2. The 2,296 rows are correlated synthetic transforms, not independent trials.
3. There are no unknown probes, so removing a quality override could worsen FPIR unseen here.
4. Stored timings are recognition-stage arithmetic, not end-to-end or Raspberry Pi measurements.
5. Validate the candidate on development-only folds, then freeze it and run a locked identity/session-disjoint open-set test before changing runtime code.
"""
    (output_dir / "README.md").write_text(readme, encoding="utf-8")

    artifact_names = [
        "results.json",
        "policy_summary.csv",
        "accept_margin_sweep.csv",
        "quality_flag_ablation.csv",
        "primary_candidate_changed_rows.csv",
        "README.md",
    ]
    provenance = {
        "status": "experimental_posthoc_smoke_not_canonical",
        "created_at_local_date": "2026-08-13",
        "source_git_commit": git_value("rev-parse", "HEAD"),
        "source_git_branch": git_value("branch", "--show-current"),
        "source_git_dirty": bool(git_value("status", "--porcelain")),
        "command": " ".join([sys.executable, str(SCRIPT_PATH), *sys.argv[1:]]),
        "python": sys.version,
        "platform": platform.platform(),
        "inputs": {
            str(records_path.relative_to(WORKSPACE_ROOT)): sha256(records_path),
            str(thresholds_path.relative_to(WORKSPACE_ROOT)): sha256(thresholds_path),
            str(reference_path.relative_to(WORKSPACE_ROOT)): sha256(reference_path),
        },
        "script_sha256": sha256(SCRIPT_PATH),
        "outputs": {name: sha256(output_dir / name) for name in artifact_names},
        "scientific_status": {
            "canonical": False,
            "citation_allowed": False,
            "reason": "Post-hoc routing replay on the same known-genuine transform battery used to identify the issue.",
        },
    }
    (output_dir / "run_provenance.json").write_text(
        json.dumps(provenance, indent=2), encoding="utf-8"
    )

    print(f"Wrote experimental smoke artifacts to {output_dir}")
    print(
        f"deployed: AR={deployed_summary['overall_ar_percent']:.4f}% "
        f"esc={deployed_summary['escalation_percent']:.4f}% "
        f"lat={deployed_summary['mean_latency_ms']:.4f}ms"
    )
    print(
        f"{primary_name}: AR={primary_summary['overall_ar_percent']:.4f}% "
        f"esc={primary_summary['escalation_percent']:.4f}% "
        f"lat={primary_summary['mean_latency_ms']:.4f}ms "
        f"saved_modified_calls={primary_delta['saved_sface_calls_modified_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
