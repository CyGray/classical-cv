# LS-Face Data Directory Setup

This directory is gitignored to avoid checking in large binary datasets, with the exception of this `README.md`. 

To replicate the project environment, configure the `data/` folder with the following directory structure:

```
data/
├── lasalle_db1/                               # Raw LaSalle DB1 photos (28 identities, BGR)
├── lasalle_db1_processed/                     # Pre-cropped & aligned face tiles (100x100, Tan-Triggs normalized)
├── lfw-dataset/                               # LFW DB1, ORIGINAL UNFUNNELED build, 250x250 (5,749 identities, 13,233 images)
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

## Which LFW build to use (read before downloading anything)

LFW ships in four builds: original (unaligned), funneled, LFW-a, and deep-funneled. All four are 250x250 with identical filenames, so you cannot tell them apart by looking at a filename or an image size. Only the download source tells you which one you have.

This repo uses the ORIGINAL UNFUNNELED build. `scripts/utils/setup_datasets.py` line 12 pins `LFW_URL = "https://ndownloader.figshare.com/files/5976018"` (180,566,744 bytes) and extracts it to `data/lfw-dataset`. That script is the only sanctioned way to populate that folder.

Do not substitute the Kaggle dataset `jessicali9530/lfw-dataset`. That copy is the DEEP-FUNNELED build. Deep-funneling pre-warps every face into a canonical position, which does part of the pipeline's own alignment work for it and inflates LBPH results in particular.

The frozen threshold `tau_accept = 67.03325520645528` (as of 2026-08-02; was 67.0084) was derived on the original unfunneled build. Mixing builds silently changes LBPH distances and invalidates that threshold. If you ever run a funneled or deep-funneled leg, label it explicitly as a separate ablation and never pool its distances with original-build numbers.

## Do not source gallery or probe images from processed trees

Any folder whose name contains `_processed`, or which holds exactly one image per identity, or whose images are smaller than 250x250, is a derived artifact. It is never a valid source for building a gallery/probe split.

Known bad sources, listed by name so nobody rediscovers them: `data/lfw/{light,medium,heavy}` (augmented legs), and any external `lfw_processed/` tree (one image per identity, downscaled to 100x100).

Reason: an earlier pipeline stage collapsed LFW to one image per identity and resized to 100x100. Discarding the second image is what made a gallery/probe-disjoint split impossible and produced the invalid ~99% Accuracy Ratio results. Of LFW's 5,749 identities, 1,680 have two or more images; those 1,680 are the entire probe pool, and a one-image-per-identity tree destroys it.

Modification severities are resolution-dependent. A 7-pixel blur kernel covers roughly 3 percent of a 250-pixel face but roughly 7 percent of a 100-pixel face, and JPEG's fixed 8x8 blocks cover 2.5x more face area at 100px. Robustness numbers generated at 100x100 are not comparable to numbers generated at 250x250.

Keep images at native 250x250 through modification and let each engine do its own resize at match time: LBPH normalizes to 100x100 via `IMG_SIZE` in `src/classical_faces/preprocess.py`, and SFace align-crops to 112x112 in `src/sface/recognizer.py`. Pre-downscaling to 100x100 forces SFace to upsample 100 to 112, which invents pixels and understates SFace.

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
