"""Declarative form specs for the highest-traffic actions (DESIGN.md §5.2 / BUILD.md 3.1).

Each field maps a high-level UI choice to the SAME argv tokens main.py's interactive
prompts would build (prompt_independence_dataset_args, prompt_core_dataset_args,
prompt_hybrid_args, etc.) — so submitting a form runs exactly what the menu would,
minus the input() loop. Every form also gets an implicit free-form "extra args" box
server-side, so anything a form doesn't expose is still reachable.

The ACTION SET here is asserted to be a subset of action_registry.list_groups() at
import-check time (see form_fields_selfcheck / the test in app startup), so a renamed
or removed main.py action fails loudly instead of drifting.

Field schema (JSON-serialisable, consumed by /api/actions/form-fields):
  { name, label, type: select|text|number|checkbox, help?, default?,
    options?: [{ value, label, args: [str, ...] }],   # select
    flag?: "--foo",                                    # text/number -> [flag, value]
    args?: [str, ...] }                                # checkbox -> args when checked
"""

from __future__ import annotations

from typing import Any

# ---- Reusable field builders -------------------------------------------------

def _independence_dataset_field() -> dict:
    """Mirror prompt_independence_dataset_args: --dataset-dir per choice."""
    return {
        "name": "dataset",
        "label": "Dataset",
        "type": "select",
        "help": "Which pre-cropped face set to sweep. Matches the menu's dataset picker.",
        "default": "lasalle_db1",
        "options": [
            {"value": "lasalle_db1", "label": "La Salle DB1 (processed)",
             "args": ["--dataset-dir", "data/lasalle_db1_processed"]},
            {"value": "lsdb2_light", "label": "LSDB2 — light (DB1 augmented)",
             "args": ["--dataset-dir", "data/split_augmented41mods_lasalle_clean/light/train"]},
            {"value": "lsdb2_medium", "label": "LSDB2 — medium (DB1 augmented)",
             "args": ["--dataset-dir", "data/split_augmented41mods_lasalle_clean/medium/train"]},
            {"value": "lfw1", "label": "LFW 1",
             "args": ["--dataset-dir", "data/lfw-dataset"]},
            {"value": "lfw2_light", "label": "LFW 2 — light (LFW1 augmented)",
             "args": ["--dataset-dir", "data/split_augmented41mods/light/train"]},
            {"value": "lfw2_medium", "label": "LFW 2 — medium (LFW1 augmented)",
             "args": ["--dataset-dir", "data/split_augmented41mods/medium/train"]},
        ],
    }


def _iterations_field(default: str = "") -> dict:
    return {
        "name": "iterations",
        "label": "Iterations",
        "type": "number",
        "flag": "--iterations",
        "default": default,
        "help": "Seeded repeats to pool over. Paper protocol is 10; blank = script default.",
    }


def _output_dir_field() -> dict:
    return {
        "name": "output_dir",
        "label": "Output directory (optional)",
        "type": "text",
        "flag": "--output-dir",
        "default": "",
        "help": "Repo-relative, e.g. reports/independence/hybrid/lsdb1_i10. Blank = script default.",
    }


def _classical_dataset_source_field(is_training: bool) -> dict:
    """Simplified mirror of prompt_core_dataset_args. The clean split is the 90% case
    and the recommended, leakage-free default; raw/LFW sources stay reachable via the
    Terminal tab, which runs the full interactive picker."""
    clean_raw = "train" if is_training else "test"
    return {
        "name": "dataset_source",
        "label": "Dataset source",
        "type": "select",
        "default": "clean",
        "help": "Clean split is the recommended leakage-free set. For raw / LFW / 'both', use the Terminal tab's full picker.",
        "options": [
            {
                "value": "clean",
                "label": "La Salle CLEAN split (recommended, pre-cropped)",
                "args": [
                    "--base-data-dir", "data/split_lasalle",
                    "--raw-dir-name", clean_raw,
                    "--processed-dir-name", "lasalle_db1_processed",
                    "--include-raw", "--assume-cropped",
                    "--aug-splits", "__disabled__",
                ] + (["--no-include-augmented"] if not is_training else []),
            },
        ],
    }


def _detector_field() -> dict:
    return {
        "name": "detector",
        "label": "Face detector",
        "type": "select",
        "default": "",
        "help": "Only affects raw/LFW inputs; the clean split skips detection.",
        "options": [
            {"value": "", "label": "Script default", "args": []},
            {"value": "haar", "label": "Haar / Viola-Jones", "args": ["--detector", "haar"]},
            {"value": "yunet", "label": "YuNet (CNN)", "args": ["--detector", "yunet"]},
        ],
    }


def _hybrid_mode_field() -> dict:
    return {
        "name": "mode",
        "label": "Hybrid mode",
        "type": "select",
        "default": "cascade",
        "help": "cascade = LBPH fast path + SFace escalation (deployed default).",
        "options": [
            {"value": "cascade", "label": "cascade (deployed)", "args": ["--mode", "cascade"]},
            {"value": "cv_only", "label": "cv_only (LBPH only)", "args": ["--mode", "cv_only"]},
            {"value": "dl_only", "label": "dl_only (SFace only)", "args": ["--mode", "dl_only"]},
        ],
    }


# ---- The form registry -------------------------------------------------------
# Keyed by (model, action_label) exactly as they appear in GROUPED_CHOICES.

def _classical_forms(model: str) -> dict[tuple[str, str], list[dict]]:
    return {
        (model, "train"): [_classical_dataset_source_field(is_training=True), _detector_field()],
        (model, "evaluate"): [_classical_dataset_source_field(is_training=False), _detector_field()],
        (model, "independence test"): [_independence_dataset_field(), _iterations_field(), _output_dir_field()],
        (model, "independence test (light front)"): [
            {
                "name": "note",
                "label": "Light-front independence",
                "type": "note",
                "help": "Runs the La Salle processed light-front sweep. For LFW segment modes, use the Terminal tab.",
            },
            _output_dir_field(),
        ],
    }


FORMS: dict[tuple[str, str], list[dict]] = {}
for _m in ("LBPH", "Eigenfaces", "Fisherfaces"):
    FORMS.update(_classical_forms(_m))

FORMS.update({
    ("Hybrid", "enroll"): [
        {"name": "note", "label": "Enroll SFace gallery", "type": "note",
         "help": "Builds models/sface/gallery.npy from defaults. No options needed."},
    ],
    ("Hybrid", "evaluate"): [
        _hybrid_mode_field(),
        {"name": "impostors", "label": "Include LFW impostors (open-set FAR)", "type": "checkbox",
         "default": False, "args": ["--impostor-dir", "data/lfw-dataset"]},
    ],
    ("Hybrid", "independence test (joint cv+dl+cascade)"): [
        _independence_dataset_field(),
        _iterations_field(default="10"),
        _output_dir_field(),
    ],
    ("Hybrid", "accuracy ratio (41-mod: cv vs dl vs cascade)"): [
        {"name": "note", "label": "41-mod accuracy ratio", "type": "note",
         "help": "Runs the 4-mode cv/dl/cascade/parallel suite with defaults."},
    ],
})


# ---- API + argv assembly -----------------------------------------------------

def form_for(model: str, action: str) -> list[dict] | None:
    return FORMS.get((model, action))


def has_form(model: str, action: str) -> bool:
    return (model, action) in FORMS


def build_args(model: str, action: str, values: dict[str, Any]) -> list[str]:
    """Translate submitted field values into argv tokens, in field order."""
    fields = FORMS.get((model, action)) or []
    args: list[str] = []
    for f in fields:
        name = f["name"]
        ftype = f["type"]
        val = values.get(name)
        if ftype == "select":
            opts = f.get("options", [])
            chosen = next((o for o in opts if o["value"] == val), None)
            if chosen is None and f.get("default") is not None:
                chosen = next((o for o in opts if o["value"] == f["default"]), None)
            if chosen:
                args.extend(chosen.get("args", []))
        elif ftype in ("text", "number"):
            if val not in (None, "", []):
                args.extend([f["flag"], str(val)])
        elif ftype == "checkbox":
            if val:
                args.extend(f.get("args", []))
        # "note" contributes nothing
    return args


def is_evaluation_action(action: str) -> bool:
    return action.startswith("evaluate")


def selfcheck(existing_pairs: set[tuple[str, str]]) -> list[tuple[str, str]]:
    """Return any (model, action) in FORMS that is NOT a real GROUPED_CHOICES pair."""
    return [pair for pair in FORMS if pair not in existing_pairs]
