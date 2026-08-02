"""Shared dataset enumeration for the classical recognizers.

One copy of the logic that turns a base data directory plus a set of
include-flags into a flat list of ``(bucket, person, person_dir)`` entries.
Used identically by training and evaluation so both stages always agree on what
"the data" is.
"""

import os
import random
from pathlib import Path

from src.dataset_layout import gather_augmented_person_dirs, infer_target_split_name

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def root_path(*parts: str) -> str:
    return str(PROJECT_ROOT.joinpath(*parts))


def resolve_path(path_value: str) -> str:
    candidate = Path(path_value)
    if candidate.is_absolute():
        return str(candidate)
    return str(PROJECT_ROOT.joinpath(candidate))


def is_image_file(file_name: str) -> bool:
    _, ext = os.path.splitext(file_name)
    return ext.lower() in ALLOWED_EXTENSIONS


def list_image_files(folder: str) -> list[str]:
    return [f for f in sorted(os.listdir(folder)) if is_image_file(f)]


def stable_person_seed(base_seed: int, bucket: str, person: str) -> int:
    token = f"{bucket}:{person}"
    return base_seed + sum(ord(ch) for ch in token)


def _gather_person_dirs(root: str, bucket: str) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    if not os.path.isdir(root):
        return out
    for person in sorted(os.listdir(root)):
        person_path = os.path.join(root, person)
        if os.path.isdir(person_path):
            out.append((bucket, person, person_path))
    return out


def gather_dataset_entries(
    *,
    base_data_dir: str,
    raw_dir: str,
    processed_dir: str,
    aug_dir: str,
    aug_splits: set[str],
    include_raw: bool,
    include_processed: bool,
    include_augmented: bool,
) -> list[tuple[str, str, str]]:
    """Return ``(bucket, person, person_dir)`` entries for the selected sources.

    ``bucket`` is one of ``"raw"``, ``"processed"`` or ``"augmented/<split>[/<train|test>]"``.
    The augmented split is restricted to ``target_split`` (train/test) when the
    raw/processed folder name implies one, so a train run never pulls augmented
    *test* images and vice-versa.
    """
    entries: list[tuple[str, str, str]] = []

    if include_raw:
        entries.extend(_gather_person_dirs(os.path.join(base_data_dir, raw_dir), "raw"))

    if include_processed:
        entries.extend(
            _gather_person_dirs(os.path.join(base_data_dir, processed_dir), "processed")
        )

    if include_augmented:
        augmented_root = os.path.join(base_data_dir, aug_dir)
        target_split = infer_target_split_name(raw_dir=raw_dir, processed_dir=processed_dir)
        entries.extend(
            gather_augmented_person_dirs(
                augmented_root=augmented_root,
                aug_splits=aug_splits,
                target_split=target_split,
            )
        )

    return entries


def sample_image_files(
    folder: str,
    *,
    max_images: int,
    already_used: int,
    bucket: str,
    person: str,
    random_seed: int,
) -> list[str]:
    """List image files for a person folder, applying an optional per-person cap.

    When capping, files are shuffled with a deterministic per-(bucket, person)
    seed so repeated runs select the same subset.
    """
    image_files = list_image_files(folder)
    if max_images <= 0:
        return image_files

    remaining = max_images - already_used
    if remaining <= 0:
        return []
    rng = random.Random(stable_person_seed(random_seed, bucket, person))
    shuffled = list(image_files)
    rng.shuffle(shuffled)
    return shuffled[:remaining]
