# TODO — build the actual 41-modification generator, verified against `table.png`

## Problem

`table.png` (see `README.md` in this folder for the full text transcription)
is the spec of record for the robustness test's 41 (modification, tier)
variants. Right now, **nothing in this repo actually applies these
modifications to images per that spec**:

- `deep-learning/ar-table.py`'s `MODIFICATION_MAPS` only *labels* filename
  suffixes with `(category, tier)` for scoring a pre-built `.npy` feature
  database. It assumes the modified images already exist; it contains no
  image-transform code at all.
- The real image-generation pipeline that produced whatever modified images
  the DL track scored is external to this repo (per project memory: DL
  track is untracked, `D:/`-hardcoded, not present here). We cannot inspect
  or verify it from this repo.
- `classical-cv/src/benchmark/modifications.py` has its own `_DL41_FN_LEVEL`
  transform implementations under the `dl41` mod-set, but its own module
  comment (lines 93–103) explicitly disclaims that these are only a
  "reasonable-best implementation of what each name conventionally means" —
  pinned to the DL spec's *names and tiers*, not verified bit-for-bit
  against `table.png`'s actual numeric definitions.

So: category/tier labels are consistent everywhere (41/41, verified), but
the actual pixel-level modification math has never been checked against
`table.png` as ground truth, in either track.

## What "done" looks like

A single, reviewed implementation (one canonical module, imported by both
tracks rather than re-implemented per-track) that:

1. Takes a source image and a `(modification, tier)` pair from
   `README.md`'s table and produces the modified image per the table's
   literal parameters.
2. Has been checked, modification-by-modification, against `README.md`
   (not against memory of the table — re-read the transcription) for:
   - **Brightness**: confirm multiplicative vs. additive interpretation of
     "+25%/+20%/+10%" (current classical-cv code assumes multiplicative
     gain — confirm that's actually intended).
   - **Monochrome**: implement `I = 0.299R + 0.587G + 0.114B` exactly
     (this is the ITU-R BT.601 luma formula — confirm current code doesn't
     silently use OpenCV's default `cv.COLOR_BGR2GRAY`, which uses the same
     coefficients but in a different channel order given BGR vs RGB input —
     verify no R/B swap bug).
   - **JPEG compression**: QF 30/60/80 — confirm which encoder/library and
     that quality-factor semantics match (OpenCV vs PIL vs libjpeg can
     differ slightly).
   - **Color reduction**: "GIF 8bit version" (medium) vs "16bit: RGB(565)"
     (light) — confirm whether "GIF 8bit" means an actual adaptive/web-safe
     256-color palette quantization (GIF's real behavior) or a naive
     3-3-2-bit-per-channel reduction (what classical-cv currently does).
     These are not the same algorithm and will not produce the same pixels.
   - **Gaussian noise**: sigma 12.0/8.0/4.0 — confirm noise is added on the
     correct value range (0–255 vs 0–1) and correct color space.
   - **Histogram equalization** / **Auto-level**: confirm exact method
     (global vs per-channel vs luminance-only; percentile clip points for
     auto-level) — table just says "YES", so the concrete algorithm is an
     implementation decision that should be documented once chosen.
   - **Blur**: mask size 7×7/5×5/3×3 — confirm kernel type (box vs
     Gaussian) and that "mask size" means kernel dimensions, not sigma.
   - **Rotation (large-angle)**: 270°/180°/90° — confirm rotation direction
     (CW vs CCW) and that these are lossless/canonical rotations (no
     interpolation/border artifacts), since 90/180/270 don't need any.
   - **Rotation (small-angle)**: 45°/25°/10° — confirm direction and
     border-fill/interpolation choice, since these do need resampling.
   - **Scaling**: 50%/70%/90% "width-height ratio" — confirm this means
     uniform zoom (both dimensions scaled together) vs. an actual
     width:height *ratio* change (which would be a squash, not a zoom) —
     the table's own wording ("width-height ratio") is ambiguous against
     "Aspect ratio change" being a separate row below it.
   - **Translation**: 30%/20%/10% — confirm "% of what" (image width?
     height? min(h,w)?) and direction/axis.
   - **Flip**: left-right only — trivial, but confirm no double-flip bug
     (see `classical-cv`'s own note about a stray `flip_twice` variant found
     in `data/lfw/{light,medium,heavy}` that is NOT part of this spec and
     must not be reintroduced).
   - **Aspect ratio change**: 4:3→6:3 (medium) / 4:3→16:9 (light) — **first
     resolve the "(1.5 equiv)" / "(1.33 equiv)" numbers noted in
     `README.md`** before implementing; as transcribed they don't match
     their own target ratios' width/height quotients, so either the table's
     parenthetical is a typo, or "equiv" means something other than a
     width/height quotient (e.g. equiv. squash factor). Do not guess
     silently — the parameter that goes into the actual squash transform
     depends on resolving this.
   - **Crop**: 60%/70%/90% — confirm this is area retained (not linear
     dimension retained — those give very different crops) and that the
     crop is centered.
   - **Skew**: +10/+6/+4 deg — confirm axis (horizontal vs vertical shear)
     and sign convention.
   - **Perspective (focal length=500)**: +10/+6/+4 deg — confirm what
     "focal length=500" is actually used for in the projection math (the
     current classical-cv implementation does a simple keystone warp keyed
     only on the degree value and does not reference a focal length at
     all — this needs an actual camera-model-based implementation or an
     explicit note on why focal length is not needed).
3. Is used to (re)generate the actual robustness-test image set, replacing
   reliance on the external/untracked DL pipeline, so results in this repo
   are reproducible end-to-end from `table.png`'s spec.
4. Replaces or is adopted by `classical-cv/src/benchmark/modifications.py`'s
   `_DL41_FN_LEVEL` once verified, so there's one implementation instead of
   an unverified "reasonable-best" one.

## Out of scope for this TODO

- Re-deriving the DL track's historical results (those numbers stay as
  reported; this is about making the *modification generation* itself
  correct and reproducible going forward).
