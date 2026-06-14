# Independence Test Algorithm Report (Light Front)

## 1. Purpose of the scripts

The `independence_test_light_front.py` scripts for LBPH, Eigenfaces, and Fisherfaces all answer one core question:

- If we compare one person against all other people, how often does the system wrongly say two different people are similar enough to be accepted?

In this test setup:

- One image per person is used (usually `light_front.jpg`).
- Every comparison is between different identities.
- Any accepted pair is treated as a false positive.

So the main measurement is false positive rate (FPR):

- `FPR = false positives / total inter-identity comparisons`

## 2. High-level flow shared by all three scripts

All three scripts follow the same overall pipeline:

1. Read command-line options (dataset, thresholds, output settings, speed settings).
2. Resolve dataset path and output path.
3. Collect person folders.
4. Pick one image per person (`light_front.jpg` or first valid image when needed).
5. Preprocess each selected image into a clean grayscale face.
6. Train one recognizer on all selected identities.
7. Extract each identity’s internal feature vector from the trained model.
8. Compute pairwise distances across identities.
9. Normalize distances to a 0-100 scale.
10. Build statistics and candidate thresholds.
11. Compute threshold sweep and optional provided-threshold FPR.
12. Save CSV outputs, plots, and `summary.json`.
13. If segmented runs are enabled, try merging segment outputs.

## 3. Input and configuration stage

Each script starts by parsing many options. Important ones:

- Dataset controls: `--dataset-source`, `--dataset-dir`, `--image-name`
- Preprocessing controls: `--min-face-size`, `--align-eyes`, `--equalization`, `--downscale-max-side`
- Evaluation controls: `--threshold`, `--max-identities`, `--max-comparisons`
- Large-run controls: `--streaming-threshold`, `--segment-count`, `--segment-index`, `--workers`
- Output controls: `--output-dir`, `--write-comparisons-csv`

Then it chooses defaults:

- If no dataset path is provided, it selects a preset (`lasalle_db1_processed` or `lfw-dataset`).
- If using LFW and `light_front.jpg` is not appropriate, it switches to “first available image.”
- It auto-selects output subfolders based on dataset and segmentation mode.

## 4. Dataset scan and image selection

The scripts:

1. List all identity folders under the dataset root.
2. For each identity, select:
   - exact `light_front.jpg`, or
   - first valid image if `__first__` mode is active.
3. Build an identity-to-image map for the next stages.

This ensures there is exactly one chosen image per person for this test.

## 5. Face preprocessing stage

For every selected image:

1. Load the file.
2. Convert it to grayscale.
3. Run face extraction and cleanup (`extract_lbph_face`), which may include:
   - face localization,
   - optional eye-based alignment,
   - contrast equalization (`equalize` or `clahe`),
   - resizing to the model’s expected input size.
4. If preprocessing fails (unreadable/no face/too small), skip identity and record skip reason.
5. If successful, keep processed face and assign numeric label.

The script tracks counters like:

- processed
- successful
- skipped_unreadable
- skipped_no_face
- skipped_too_small

## 6. Feature extraction strategy (shared core helper)

The scripts call `train_and_extract_features(...)` from `src/independence_common.py`.

That helper does this:

1. Sort identities to ensure stable order.
2. Train one model on all faces at once.
3. Save model to a temporary YAML file.
4. Re-open that file and read the model’s stored feature representation per identity.
5. Return feature matrix + identity order.
6. Delete temporary file.

Model-specific extraction:

- LBPH: reads histogram vectors from `opencv_lbphfaces`.
- Eigenfaces: reads projection vectors from `opencv_eigenfaces`.
- Fisherfaces: reads projection vectors from `opencv_fisherfaces`.

This gives one comparable vector per identity for pairwise distance calculations.

## 7. Pairwise comparison stage

The scripts compare identities in pairs and compute distances:

- Lower distance means “more similar.”
- Since pairs are different people, low distance is risky.

Distance type:

- LBPH uses chi-squared distance.
- Eigenfaces uses Euclidean distance.
- Fisherfaces uses Euclidean distance.

There are two execution modes:

- Standard mode: in-memory full record generation.
- Streaming mode (for very large runs): memory-mapped arrays + chunked worker processes.

Streaming mode details:

- Splits work into chunks of identity rows.
- Workers compute distances for chunks.
- Main process appends raw distances to on-disk memmap.
- Keeps a heap of lowest distances (most concerning pairs).
- Optionally skips full `comparisons.csv` for speed unless requested.

Segmentation:

- LBPH segmenting is by identity row ranges.
- Eigenfaces/Fisherfaces segmenting is by pair-count ranges for better balance.

## 8. Distance normalization and statistics

After raw distances are collected:

1. Find global min and max raw distance.
2. Convert each raw value to normalized `0..100`:
   - near `0` means most similar pair in run,
   - near `100` means least similar pair in run.
3. Compute summary statistics:
   - min, max, mean, median, std dev
   - percentiles (1, 5, 10, 25, 50, 75, 90, 95, 99)

These normalized values are used in outputs and threshold evaluation.

## 9. Threshold logic and false positives

Candidate thresholds are automatically built from impostor-distance distribution:

- p01, p05, p10, p25 percentiles
- mean minus one standard deviation

Then for each threshold:

1. Count distances `<= threshold`.
2. Treat these as false positives.
3. Compute FPR.

If user gives `--threshold`, it also computes a dedicated provided-threshold FPR.

## 10. Saved outputs

Each run writes artifacts such as:

- `comparisons.csv` (optional in large streaming runs)
- `threshold_sweep.csv`
- `lowest_distance_pairs.csv`
- `distance_histogram.png`
- `distance_curve_plot.png`
- `summary.json`

`summary.json` includes:

- dataset counts
- preprocessing outcomes
- comparison counts and segmentation metadata
- distance statistics
- candidate thresholds
- threshold sweep results
- lowest-distance pairs
- output file paths

## 11. Plot generation

Two visualizations are generated from normalized distances:

- Histogram: shows observed distribution.
- Smooth density curve (KDE): shows trend shape.

If a threshold is supplied, plots indicate where false positives live (left side under threshold).

For huge runs, plotting may use sampled points to keep plotting practical.

## 12. Differences between LBPH, Eigenfaces, and Fisherfaces scripts

Most code flow is intentionally parallel. Main differences are:

1. Model used:
   - LBPH recognizer
   - EigenFace recognizer
   - FisherFace recognizer
2. Distance function:
   - LBPH: chi-squared
   - Eigen/Fisher: Euclidean
3. Streaming worker setup:
   - Eigen/Fisher include BLAS/thread controls for numeric operations.
4. Feature caching:
   - Eigen/Fisher scripts include reusable feature caching for LFW runs.
5. Segment balancing:
   - Eigen/Fisher split by pair-workload.
   - LBPH splits more directly by row block.

## 13. End-to-end summary in plain words

From start to finish, each script:

1. Chooses one image per person.
2. Cleans and standardizes each face.
3. Builds one model that “understands” all included identities.
4. Pulls out each identity’s internal numeric face signature.
5. Compares everyone against others by distance.
6. Converts distances to a common 0-100 scale.
7. Measures how often different people look “too close” under candidate thresholds.
8. Writes reports and plots so threshold choices can be made with evidence.
