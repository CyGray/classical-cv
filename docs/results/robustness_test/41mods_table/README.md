# 41 Modifications Table — `table.png`

Text transcription of `docs/41mods_table/table.png`, the reference spec for the
41-modification robustness test used by both the `deep-learning/` and
`classical-cv/` tracks (see `deep-learning/ar-table.py`'s `MODIFICATION_MAPS`
and `classical-cv/src/benchmark/modifications.py`'s `DL41_CATEGORY_TIER`).

The image is a table with a "Levels" header spanning three columns —
**heavy**, **medium**, **light** — and one row per modification
("Modifications", left column). `N/A` means that modification has no variant
at that severity level (it is a single-tier modification). Below, everything
that is not a table cell (e.g. formulas) is transcribed verbatim.

## Photometric / pixel-value modifications

| Modification | Heavy | Medium | Light |
|---|---|---|---|
| Brightness change | +25% | +20% | +10% |
| Color to monochrome conversion | N/A | N/A | `I = 0.299·R + 0.587·G + 0.114·B` |
| JPEG compression with varying Quality factors | QF 30 | QF 60 | QF 80 |
| Color reduction | N/A | GIF 8bit version | 16bit: RGB(565) |
| Gaussian Noise ▼ | 12.0 | 8.0 | 4.0 |
| Histogram equalization ♦ | N/A | N/A | YES |
| Image enhancement via Auto-level | N/A | N/A | YES |
| Blur | Mask size: 7×7 | Mask size: 5×5 | Mask size: 3×3 |

Notes on this block:
- "Color reduction" has no heavy tier — only medium (GIF 8-bit) and light
  (16-bit RGB565).
- "Gaussian Noise" and "Histogram equalization" carry footnote markers (▼
  and ♦ respectively) in the source image; no footnote text is visible in
  the cropped table — the markers exist but their referent text is not part
  of the captured image.
- "Histogram equalization" and "Image enhancement via Auto-level" are
  each single-tier (light-only, value "YES") — heavy/medium are N/A.

## Geometric transformation

This block is a single grouped row labeled "Geometric transformation" in the
image's left margin, spanning eight sub-rows. **The first two sub-rows are
both literally labeled "Rotation"** in the image — they are two distinct
modifications that happen to share a display name (large-angle canonical
rotation vs. small-angle rotation); they are disambiguated below as
"Rotation (large-angle)" and "Rotation (small-angle)" for clarity.

| Sub-modification | Heavy | Medium | Light |
|---|---|---|---|
| Rotation (large-angle) | 270° | 180° | 90° |
| Rotation (small-angle) | 45° | 25° | 10° |
| Scaling (width-height ratio) | 50% | 70% | 90% |
| Translation | 30% | 20% | 10% |
| Flip | N/A | N/A | left-right |
| Aspect ratio change | N/A | 4:3 → 6:3 (1.5 equiv) | 4:3 → 16:9 (1.33 equiv) |
| Crop° | 60% | 70% | 90% |
| Skew | +10deg | +6deg | +4deg |
| Perspective (Focal length=500) | +10deg | +6deg | +4deg |

Notes on this block:
- "Crop" carries a `°` marker in the source image next to the label (likely
  a footnote reference, same caveat as the ▼/♦ markers above — no footnote
  text is present in the captured image).
- "Flip" is single-tier (light-only, "left-right").
- "Aspect ratio change" has no heavy tier — only medium ("4:3→6:3
  (1.5 equiv)") and light ("4:3→16:9 (1.33 equiv)"), transcribed exactly as
  printed. Note for implementers: the "equiv" decimal shown for each target
  ratio does not match that target ratio's own width/height quotient
  (6:3 = 2.0, not 1.5; 16:9 ≈ 1.78, not 1.33 — 1.33 is actually 4:3, the
  *source* ratio). Do not silently "correct" this when implementing —
  resolve it deliberately first; see `TODO.md`.
- "Perspective" is explicitly qualified with "(Focal length=500)" as part of
  its row label, and its heavy/medium/light values are all given in degrees
  (+10deg / +6deg / +4deg), same shape as Skew.

## Row/column count

12 modification families × up to 3 tiers each = **41 total (modification,
tier) variants**, matching the filename `41mods_table` and the 41-entry
`MODIFICATION_MAPS` / `DL41_CATEGORY_TIER` dicts referenced above:

- 3-tier families (heavy/medium/light, 3 variants each): Brightness change,
  JPEG compression, Gaussian Noise, Blur, Rotation (large-angle), Rotation
  (small-angle), Scaling, Translation, Crop, Skew, Perspective = 11 families
  × 3 = 33
- 2-tier families (medium/light only, 2 variants each): Color reduction,
  Aspect ratio change = 2 families × 2 = 4
- 1-tier families (light only, 1 variant each): Color to monochrome
  conversion, Histogram equalization, Auto-level, Flip = 4 families × 1 = 4

33 + 4 + 4 = **41**.

## Known consumers in this repo

- `deep-learning/ar-table.py` — `MODIFICATION_MAPS` (lines 15–57): maps
  filename suffixes (e.g. `brightness_p25`, `gaussnoise_12`, `persp_10`) to
  `(category, tier)` for scoring an already-built `.npy` feature database.
  This file does **not** generate images — see `TODO.md`.
- `classical-cv/src/benchmark/modifications.py` — `DL41_CATEGORY_TIER`
  (verbatim copy of the mapping above) plus `_DL41_FN_LEVEL`, its own
  best-effort pixel-transform implementations. Its module comment explicitly
  states these are *not* guaranteed bit-identical to whatever pipeline
  actually generated the DL-side modified images — only the names/tiers are
  pinned to this table.
