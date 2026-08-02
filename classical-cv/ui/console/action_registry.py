"""Single source of truth for what actions exist: main.GROUPED_CHOICES, read live.

DESIGN.md §5.2 requires the console to derive its action list from main.py rather than
hand-copying it, so the two surfaces can't drift. main.py's module scope was audited
(only imports + constant/function definitions; main() is guarded behind
`if __name__ == "__main__"`), so a plain `import main` is side-effect-safe here — no
input() prompt, no print, no file write happens at import time. Reusing main's own
helpers (get_python_command, resolve_path, build_subprocess_env, run_choice's argv
shape, warn_if_missing_auto_artifacts) is preferable to reimplementing them: it keeps
the console faithful to exactly what the menu does.
"""

from __future__ import annotations

import functools
import os
import sys
from pathlib import Path

# Repo root = two levels up from ui/console/. Put it on sys.path so `import main` works
# regardless of the cwd uvicorn was launched from.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@functools.lru_cache(maxsize=1)
def _main_module():
    import main  # noqa: E402  (deliberately late; see module docstring)

    return main


def list_groups() -> list[dict]:
    """[{model, actions: [{label, script}]}] — mirrors /api/actions (DESIGN.md §5.6)."""
    main = _main_module()
    out: list[dict] = []
    for model_name, actions in main.GROUPED_CHOICES:
        out.append(
            {
                "model": model_name,
                "actions": [
                    {"label": label, "script": script} for (label, script) in actions
                ],
            }
        )
    return out


def action_pairs() -> set[tuple[str, str]]:
    """Every (model, action_label) pair that exists — for the form_fields subset check."""
    pairs: set[tuple[str, str]] = set()
    for group in list_groups():
        for a in group["actions"]:
            pairs.add((group["model"], a["label"]))
    return pairs


def resolve_script(model: str, action: str) -> str | None:
    """Repo-relative script path for a (model, action) pair, or None if unknown."""
    for group in list_groups():
        if group["model"] != model:
            continue
        for a in group["actions"]:
            if a["label"] == action:
                return a["script"]
    return None


@functools.lru_cache(maxsize=1)
def _hardware_profile() -> dict:
    """Reuse main's hardware profile (for BLAS thread caps). Fall back to a safe minimum
    so the console still runs if profile building ever fails."""
    main = _main_module()
    try:
        return main.load_or_build_hardware_profile()
    except Exception:
        cpus = os.cpu_count() or 4
        return {"blas_threads": max(1, cpus // 2)}


def build_command(model: str, action: str, args: list[str]) -> list[str] | None:
    """Build the exact argv run_choice would build for a scripted (non-segment) run:
    [*python, resolve_path(script), *args]. Returns None for an unknown action."""
    main = _main_module()
    rel_script = resolve_script(model, action)
    if rel_script is None:
        return None
    script_path = main.resolve_path(rel_script)
    return [*main.get_python_command(), str(script_path), *args]


def subprocess_env() -> dict:
    """PYTHONPATH-prepended, BLAS-capped env — reuses main.build_subprocess_env."""
    main = _main_module()
    return main.build_subprocess_env(_hardware_profile())


def main_py_command() -> list[str]:
    """argv for launching the interactive menu itself (Terminal tab)."""
    main = _main_module()
    return [*main.get_python_command(), str(PROJECT_ROOT / "main.py")]


def check_missing_artifacts(args: list[str], is_evaluation: bool) -> list[str]:
    """Reuse main.warn_if_missing_auto_artifacts to catch 'evaluate without a model'
    the same way the menu does (DESIGN.md §5.2). Returns the list of missing paths."""
    main = _main_module()
    # main's function also prints; capture is unnecessary — we only need the return.
    return main.warn_if_missing_auto_artifacts(args, is_evaluation)
