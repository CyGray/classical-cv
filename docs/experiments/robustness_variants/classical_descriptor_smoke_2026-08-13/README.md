# Exploratory one-shot classical descriptor robustness smoke test

> **Exploratory / diagnostic / non-canonical.** Do not cite this directory as canonical evidence, modify manuscript claims from it, or use it to recalibrate frozen thresholds.

## Objective

Test whether LTP- or LPQ-family descriptors look competitive enough with a freshly rerun one-shot LBPH baseline under the current 41-modification robustness battery to justify a controlled follow-up as the cascade's cheap first stage.

## Headline ranking (strict detector + matcher system view)

| Algorithm | Clean R1 | 41-mod R1 | Delta vs LBPH | Matcher-only R1 | p50 ms | Descriptor bytes | Distance AUC | -Margin AUC |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| LPQ (w=7) | 21.43% | 16.55% | +3.14 pp | 17.45% | 8.716 | 65,536 | 0.661 | 0.774 |
| Multi-scale LPQ (3/5/7) | 21.43% | 16.55% | +3.14 pp | 17.45% | 26.191 | 196,608 | 0.628 | 0.707 |
| Tan-Triggs + LTP | 25.00% | 16.46% | +3.05 pp | 17.36% | 12.566 | 131,072 | 0.583 | 0.617 |
| LBPH | 21.43% | 13.41% | +0.00 pp | 14.14% | 3.198 | 65,536 | 0.600 | 0.506 |
| HOG + cosine | 17.86% | 11.15% | -2.26 pp | 11.75% | 1.277 | 11,664 | 0.598 | 0.617 |
| LTP | 10.71% | 7.93% | -5.49 pp | 8.36% | 12.212 | 131,072 | 0.498 | 0.527 |

## Protocol

- Identities: 28; exactly one existing manifest gallery and one existing disjoint manifest probe per identity.
- Queries: 28 clean + 1148 modified (41 DL41 variants per probe).
- Transform contract: current `get_modification_set('dl41')`; BGR transform before grayscale; `stable_rng(42, identity, probe basename, transform, level)`; each transformed array generated once.
- Shared pipeline: one YuNet call per gallery/query, default score/NMS settings, largest-face rule, strict no-face failures.
- LSDB crop contract: `assume_cropped=True`; YuNet gates each transformed pre-cropped tile, while every classical matcher receives the same successful full 100x100 grayscale tile. No landmark alignment is applied to the classical input.
- Primary metric: threshold-free closed-set 1:N Rank-1. Frozen LBPH/SFace verification or cascade thresholds are not used.
- Shared modified-query detector failures: 59 / 1148; matcher-only denominator: 1089.
- Timing: warm recognition-only time in one process; excludes image I/O, transform generation, and YuNet. Extraction and 28-template gallery matching are timed separately.

This is a small-scale LSDB analogue of the hard LFW robustness flow, not the older same-image transform-sensitivity test and not a literal raw-LFW crop pipeline.

## Algorithms and fixed reconnaissance parameters

### LBPH

```json
{
  "algorithm": "opencv_lbph",
  "descriptor_bytes": 65536,
  "descriptor_dtype": "float32",
  "descriptor_length": 16384,
  "distance": "opencv_native_predict_collect_chi_square_equivalent",
  "distance_formula": "2*sum((a-b)^2/(a+b+1e-10))",
  "grid_x": 8,
  "grid_y": 8,
  "input_contract": "shared_100x100_raw_grayscale_tile",
  "intrinsic_preprocessing": "tan-triggs",
  "neighbors": 8,
  "preprocessing_implementation": "src.classical_faces.preprocess.normalize_face",
  "radius": 1
}
```

### LTP

```json
{
  "distance": "symmetric_chi_square_half_sum",
  "grid_x": 8,
  "grid_y": 8,
  "histogram_bins_per_half": 256,
  "histogram_normalization": "l1_per_cell_per_half",
  "input": "aligned_grayscale_0_255_no_internal_resize",
  "intrinsic_preprocessing": null,
  "neighbors": 8,
  "radius": 1,
  "sampling": "square_8_clockwise_from_northwest",
  "threshold": 5.0,
  "variant": "ltp"
}
```

### Tan-Triggs + LTP

```json
{
  "distance": "symmetric_chi_square_half_sum",
  "grid_x": 8,
  "grid_y": 8,
  "histogram_bins_per_half": 256,
  "histogram_normalization": "l1_per_cell_per_half",
  "input": "aligned_grayscale_0_255_no_internal_resize",
  "intrinsic_preprocessing": {
    "alpha": 0.1,
    "gamma": 0.2,
    "implementation": "src.classical_faces.preprocess.tan_triggs_normalize",
    "name": "tan_triggs",
    "sigma0": 1.0,
    "sigma1": 2.0,
    "tau": 10.0
  },
  "neighbors": 8,
  "radius": 1,
  "sampling": "square_8_clockwise_from_northwest",
  "threshold": 5.0,
  "variant": "tan_triggs_ltp"
}
```

### LPQ (w=7)

```json
{
  "algorithm": "local_phase_quantization",
  "decorrelation": "first_order_markov_svd_rotation",
  "descriptor_bytes": 65536,
  "descriptor_dtype": "float32",
  "descriptor_length": 16384,
  "distance": "symmetric_half_chi_square",
  "frequency_beta_by_window": [
    0.14285714285714285
  ],
  "grid_columns": 8,
  "grid_rows": 8,
  "histogram_bins_per_cell": 256,
  "histogram_normalization": "per_cell_l1",
  "input_contract": "shared_2d_grayscale_normalized_face_crop",
  "rho": 0.9,
  "static_state_bytes": 3648,
  "variant": "lpq_w7",
  "window_sizes": [
    7
  ]
}
```

### Multi-scale LPQ (3/5/7)

```json
{
  "algorithm": "local_phase_quantization",
  "decorrelation": "first_order_markov_svd_rotation",
  "descriptor_bytes": 196608,
  "descriptor_dtype": "float32",
  "descriptor_length": 49152,
  "distance": "symmetric_half_chi_square",
  "frequency_beta_by_window": [
    0.3333333333333333,
    0.2,
    0.14285714285714285
  ],
  "grid_columns": 8,
  "grid_rows": 8,
  "histogram_bins_per_cell": 256,
  "histogram_normalization": "per_cell_l1",
  "input_contract": "shared_2d_grayscale_normalized_face_crop",
  "rho": 0.9,
  "static_state_bytes": 6848,
  "variant": "lpq_multiscale_w3_5_7",
  "window_sizes": [
    3,
    5,
    7
  ]
}
```

### HOG + cosine

```json
{
  "algorithm": "histogram_of_oriented_gradients",
  "block_cells": [
    2,
    2
  ],
  "block_normalization": "opencv_l2_hys",
  "block_size": [
    20,
    20
  ],
  "block_stride": [
    10,
    10
  ],
  "block_stride_cells": [
    1,
    1
  ],
  "cell_size": [
    10,
    10
  ],
  "descriptor_bytes": 11664,
  "descriptor_dtype": "float32",
  "descriptor_length": 2916,
  "distance": "cosine",
  "gamma_correction": true,
  "input_contract": "shared_2d_grayscale_100x100_face_crop_no_resize",
  "input_conversion": "round_to_nearest_uint8",
  "l2_hys_threshold": 0.2,
  "orientation_bins": 9,
  "signed_gradients": false,
  "static_state_bytes": 0,
  "variant": "hog",
  "win_size": [
    100,
    100
  ]
}
```

## Exact one-shot image selection

Source manifest: `C:\Users\acer\Documents\USLS 4th Year\Computer Vision\classical-cv\data\splits\lasalle_db1_ident_split_seed42.json` (SHA-256 `731bcf52fec2046689442f7edb26e6b28d1b99d1fbee053402eb9de3715c47dc`). Its recorded dataset root is stale, so its relative paths were explicitly rebased to `C:\Users\acer\Documents\USLS 4th Year\Computer Vision\classical-cv\data\lasalle_db1_processed` without resampling.

Selection hash: `b58c4ec07070745e1a7c6e57036cd33722eb6576d78b3bbcbd5cd01c61e794b5`. Selected-file binding hash: `dda5f11a3b74fb4607d75736ff957074ee7639939301bf164886929b2059ae03`.

| Identity | Gallery | Probe |
|---|---|---|
| Andrew_Eroyla | `Andrew_Eroyla/light_right.jpg` | `Andrew_Eroyla/dark_down.jpg` |
| Anthony_Charles_Saltat | `Anthony_Charles_Saltat/dark_front.jpg` | `Anthony_Charles_Saltat/dark_down.jpg` |
| Anthony_Gallego | `Anthony_Gallego/dark_down.jpg` | `Anthony_Gallego/dark_front.jpg` |
| Axel_Josh_Lorayna | `Axel_Josh_Lorayna/light_up.jpg` | `Axel_Josh_Lorayna/dark_down.jpg` |
| Daniel_Ramos | `Daniel_Ramos/dark_right.jpg` | `Daniel_Ramos/dark_down.jpg` |
| Diofel_Gwen_Haresco | `Diofel_Gwen_Haresco/dark_name.jpg` | `Diofel_Gwen_Haresco/dark_down.jpg` |
| Francis_Cromwell_Tan | `Francis_Cromwell_Tan/dark_name.jpg` | `Francis_Cromwell_Tan/dark_down.jpg` |
| Francis_Miles_Ang | `Francis_Miles_Ang/dark_left.jpg` | `Francis_Miles_Ang/dark_down.jpg` |
| Jim_Jonathan_Decripito | `Jim_Jonathan_Decripito/light_up.jpg` | `Jim_Jonathan_Decripito/dark_down.jpg` |
| John_Andrei_Gayona | `John_Andrei_Gayona/dark_front.jpg` | `John_Andrei_Gayona/dark_down.jpg` |
| John_Roland_Octavio | `John_Roland_Octavio/light_right.jpg` | `John_Roland_Octavio/dark_down.jpg` |
| Joseph_Andrew_Ong | `Joseph_Andrew_Ong/light_up.jpg` | `Joseph_Andrew_Ong/dark_down.jpg` |
| Josh_Dane_Labistre | `Josh_Dane_Labistre/light_left.jpg` | `Josh_Dane_Labistre/dark_down.jpg` |
| Jul_Leo_Javellana | `Jul_Leo_Javellana/dark_front.jpg` | `Jul_Leo_Javellana/dark_down.jpg` |
| Julian_Diego_Mapa | `Julian_Diego_Mapa/light_name.jpg` | `Julian_Diego_Mapa/dark_down.jpg` |
| Kenlie_John_Maghari | `Kenlie_John_Maghari/light_down.jpg` | `Kenlie_John_Maghari/dark_down.jpg` |
| Kim_Ivan_Arigorat | `Kim_Ivan_Arigorat/dark_down.jpg` | `Kim_Ivan_Arigorat/dark_front.jpg` |
| Klein_Rhee_Sioson | `Klein_Rhee_Sioson/dark_down.jpg` | `Klein_Rhee_Sioson/dark_front.jpg` |
| Kyle_Yuan_Uy | `Kyle_Yuan_Uy/dark_front.jpg` | `Kyle_Yuan_Uy/dark_down.jpg` |
| Lorenz_Ciocon | `Lorenz_Ciocon/dark_name.jpg` | `Lorenz_Ciocon/dark_down.jpg` |
| Mary_Jade_Jakosalem | `Mary_Jade_Jakosalem/dark_name.jpg` | `Mary_Jade_Jakosalem/dark_down.jpg` |
| Michael_Andrei_Jugado | `Michael_Andrei_Jugado/light_left.jpg` | `Michael_Andrei_Jugado/dark_down.jpg` |
| Norbert_Audines | `Norbert_Audines/light_name.jpg` | `Norbert_Audines/dark_down.jpg` |
| Raean_Tamayo | `Raean_Tamayo/dark_down.jpg` | `Raean_Tamayo/dark_front.jpg` |
| Thea_Ganza | `Thea_Ganza/light_left.jpg` | `Thea_Ganza/dark_down.jpg` |
| Trixia_Marie_Garcio | `Trixia_Marie_Garcio/dark_name.jpg` | `Trixia_Marie_Garcio/dark_down.jpg` |
| Wilbert_Mijares | `Wilbert_Mijares/light_up.jpg` | `Wilbert_Mijares/dark_down.jpg` |
| Yuan_Paulo_Sebastian_Belen | `Yuan_Paulo_Sebastian_Belen/light_right.jpg` | `Yuan_Paulo_Sebastian_Belen/dark_down.jpg` |

## Environment

- OS: Windows-10-10.0.22631-SP0
- CPU: 12th Gen Intel(R) Core(TM) i5-12450H (12 logical CPUs)
- Python: 3.11.9
- OpenCV: 4.13.0; NumPy: 2.4.3; scikit-learn: 1.8.0
- Git commit: `d4cbfd1ceeb4e344f7d0cbb278f74b51afe2a66a`; dirty at run: `True`

## Caveats

- One gallery image and one probe image per identity make this intentionally harsh and high-variance; the old 10-image LSDB enrollment result is not a comparator.
- LTP/Tan-Triggs+LTP and multi-scale LPQ are same-battery exploratory variants; the best-looking variant is not independently validated.
- Raw distance values are algorithm-specific. No LBPH threshold is transferred to LTP, LPQ, or HOG.
- No-face failures are shared system failures. The matcher-only view excludes them but reports their count separately.
- The optional HOG row is contextual and did not delay the required LBPH/LTP/LPQ comparison.

## Files

- `summary.json` / `summary.csv`: headline, grouped, timing, size, and AUC results.
- `per_query_results.csv`: every algorithm/query decision, score, margin, detection status, and shared pixel/crop hashes.
- `paired_lbph_vs_candidate.csv` / `paired_per_transform.csv`: strict and matcher-only paired outcomes.
- `one_shot_manifest.json`: exact paths, file hashes, and split lineage.
- `lbph_one_shot.yml`: freshly trained one-template-per-identity OpenCV LBPH model used by this smoke test.
