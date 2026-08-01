# LS-Face Data Directory Setup

This directory is gitignored to avoid checking in large binary datasets, with the exception of this `README.md`. 

To replicate the project environment, configure the `data/` folder with the following directory structure:

```
data/
├── lasalle_db1/                               # Raw LaSalle DB1 photos (28 identities, BGR)
├── lasalle_db1_processed/                     # Pre-cropped & aligned face tiles (100x100, Tan-Triggs normalized)
├── lfw-dataset/                               # LFW DB1 processed dataset (5,749 identities)
├── split_lasalle/                             # Held-out train/test split of LaSalle DB1 (28 identities)
│   ├── train/
│   └── test/
├── split_augmented41mods_lasalle_clean/      # 41-modification robustness split of LaSalle (light/medium)
│   ├── light/
│   │   ├── train/
│   │   └── test/
│   └── medium/
│       ├── train/
│       └── test/
├── split_augmented41mods/                     # 41-modification robustness split of LFW (light/medium)
│   ├── light/
│   └── medium/
└── split_lfw/                                 # Standard split of LFW database
```

## Datasets and Purpose

1. **La Salle DB1 (`lasalle_db1` & `lasalle_db1_processed`):**
   * Primary dataset used for calibration, thresholding, and validation.
   * `lasalle_db1_processed` consists of cropped and Tan-Triggs normalized face tiles used by classical pipelines.
2. **LFW Database (`lfw-dataset` & `split_lfw`):**
   * Supplementary/transfer leg used to certify false-alarm rates (FAR) at higher resolution (up to 33M comparisons).
3. **Robustness Sets (`split_augmented41mods`):**
   * Generated splits containing the 12 types of corruptions (across 41 variations/levels) to benchmark model resilience.

## Recreating the Splits
The dataset splits and augmentations are created using orchestrator scripts located in `scripts/`:
* Run `python scripts/utils/setup_datasets.py` to organize the basic database structures.
* Run `python scripts/utils/augment_split_light_medium.py` to generate the light/medium robustness tiers.
