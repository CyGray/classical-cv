# LaSalle DB1 Face Recognition Project

This project focuses on evaluating and diagnosing face recognition algorithms (classical and deep learning) using the LaSalle DB1 dataset and LFW.

## Project Structure

- `src/`: Core implementation.
  - `arcface/`, `edgeface/`, `mobilefacenet/`: Deep learning model wrappers and evaluation.
  - `eigenfaces/`, `fisherfaces/`, `lbph/`: Classical face recognition implementations.
  - `independence_common.py`: Shared utilities for identity independence tests.
  - `reporting/`: Tools for generating reports and identity profiles.
- `independence_failure_check/`: Specialized analysis scripts for diagnostic reports.
- `data/`: Dataset storage (managed externally).
- `models/`: Trained model weights and metadata.
- `outputs/`: Raw experiment results, CSVs, and plots.
- `reports/`: Aggregated evaluation and benchmark reports.

## Engineering Standards

- **Minimal Edits:** Always perform surgical updates. Do not refactor unrelated code.
- **Conventions:** Follow existing naming and structural patterns. Use `argparse` for CLI tools.
- **Testing:** New features or fixes must be validated with tests or by running the relevant script.
- **Independence Tests:** For independence tests (Eigenfaces, Fisherfaces, LBPH), follow the 10-fold repetition pattern:
  - Run the comparison 10 times with different random seeds.
  - Store raw results in `_raw_runs/run_X/`.
  - Aggregate results using the mean.
  - Maintain consistent 0-100 normalized distance scaling.

## Key Resources

- `src/independence_common.py`: Use `train_and_extract_features`, `compute_pairwise_distances`, and `aggregate_pairwise_results` for independence tests.
- `main.py`: Central entry point for all project actions.
- `CODEX.md`: Historical context for model additions.
