# Classical Track — Research-Backed Improvement Plan

**Date:** 2026-06-12 · **Scope:** performance + footprint adjustments for LBPH / Eigenfaces / Fisherfaces,
mapped to the spec (TAR 90–95%, FAR < 100 ppm, FRR 1–5%, < 100 ms, ≥ 30 fps, feature < 1 KB) and to the
6/16 / 6/30 / 7/15 deadlines. Every recommendation cites the literature it comes from and states what it
is expected to fix in *our* measured numbers (no invented results — expectations are labelled as such).

---

## 0. Where we actually stand (from committed runs, 2026-06-10..12)

| | LBPH (tan-triggs) | Eigenfaces | Fisherfaces | Spec |
|---|---|---|---|---|
| TAR @ ~100 ppm FAR | **98.21%** ✅ | 23.21% ❌ | 10.71% ❌ | 90–95% |
| FRR | 1.79% ✅ | 76.79% ❌ | 89.29% ❌ | 1–5% |
| Mean AR (41 mods) | 85.4% | 47.7% | 30.5% | — |
| Feature size | **64 KB** ❌ | 1.1 KB ❌ | 108 B ✅ | < 1 KB |
| Model size | 32 MB (101 MB aug) | 81 MB | 8 MB | Pi context |
| Live FPS / latency | 19.9 / 50 ms | 29.0 / 34 ms | 27.8 / 36 ms | ≥30 / <100 ms |

Diagnosis, one line each:

1. **The accurate model is the heavy one.** LBPH passes the whole accuracy block but its feature is 64×
   over budget and its model file scales with training-image count (multi-GB when trained on aug/LFW).
2. **Eigen/Fisher fail verification structurally.** At the 100 ppm operating point their impostor and
   genuine distance distributions overlap massively (EER 32–36%). This is not a threshold-tuning gap.
3. **Everyone is detector-bound.** Recognizer `predict()` is sub-ms; Haar detection costs 34–50 ms/frame
   and is the sole reason nothing reaches 30 fps.
4. **LBPH's residual weaknesses** are exactly the textbook LBP failure modes: `gaussian_noise` AR 47.8%
   (12.5% heavy), `motion_blur` 68.5% (28.6% heavy), `brightness_down` 73.7% (39.3% heavy).

The plan: keep what passes (LBPH-class local texture), make it small (projection), patch its known
failure modes (LTP/LPQ), stop spending on what the literature says cannot be rescued (pixel-domain
Eigen/Fisher at low FAR), and fix the detector (the real fps/latency lever).

---

## 1. Make the winning descriptor fit the budget — **local-texture histograms + subspace projection**

This is the highest-leverage change. It converts our LBPH from "accurate but 64 KB" into a
**< 1 KB discriminative embedding**, and it is the single most-validated recipe in the classical face
literature:

- **Uniform patterns (u2).** Ojala et al.'s multiresolution LBP (TPAMI 2002) showed ~90% of natural
  micro-patterns are "uniform"; restricting the histogram to the 58 uniform codes + 1 catch-all bin keeps
  the discrimination at **59 bins instead of 256** ([Scholarpedia/LBP](http://www.scholarpedia.org/article/Local_Binary_Patterns),
  [Ahonen et al., *Face Recognition with LBP*](https://www.semanticscholar.org/paper/Face-Recognition-with-Local-Binary-Patterns-Ahonen-Hadid/32420c65f8ef0c5bd83b14c8ae662cbce73e6781)).
  Ahonen's canonical face setup is a ~7×7 region grid of u2 histograms with (weighted) χ² matching
  ([paper PDF](https://scispace.com/pdf/face-recognition-with-local-binary-patterns-530w9v6pt6.pdf)).
  Effect on us: 8×8×256×4 B = 65,536 B → 8×8×59×4 B = **15,104 B** (and ~4× faster χ² scans) before any
  projection — a pure win, no accuracy cost expected per the original studies.
- **LDA on (multi-scale) LBP histograms.** Chan, Kittler & Messer (ICB 2007) extract regional
  multi-scale uniform-LBP histograms and project them with LDA into a compact discriminative descriptor —
  state-of-the-art FERET identification / XM2VTS verification results at the time
  ([Springer](https://link.springer.com/chapter/10.1007/978-3-540-74549-5_85)). This is **exactly our
  Fisherfaces machinery applied to LBP features instead of raw pixels**, and the literature is unanimous
  that descriptor+LDA ≫ pixel+LDA.
  Effect on us: feature becomes ≤ (C−1) = 27 floats = **108 B** (identical to Fisherfaces today) or a
  PCA-whitened ~200-dim variant = 800 B; the model becomes one projection matrix (~0.5–6 MB float32
  depending on PCA stage, vs 32 MB–3.8 GB) plus 28 centroids; `predict` = one mat-vec.
- **Small-sample-size caution → shrinkage LDA.** With 28 classes × 10–12 images, plain LDA scatter
  estimates are noisy; regularized/shrinkage LDA is the standard fix in face recognition
  ([Lu et al., *Regularization studies of LDA in SSS scenarios*](https://www.sciencedirect.com/science/article/abs/pii/S0167865504002260),
  [*Regularized discriminant analysis for the SSS problem*](https://www.sciencedirect.com/science/article/abs/pii/S0167865503001673)).
  `sklearn.LinearDiscriminantAnalysis(solver="eigen", shrinkage="auto")` gives Ledoit-Wolf shrinkage for
  free (sklearn is already a project dependency).

**Design decision to make explicit (affects the independence story):** fit the projection on
(a) the 28 La Salle identities (max closed-set boost; FAR estimate then partially "sees" the projection) or
(b) a **disjoint identity set** (e.g., LFW subjects, as in Chan's FERET protocol) for an
identity-independent embedding whose LFW-impostor FAR generalizes cleanly. Run both; (b) is the
methodologically safer headline for the independence test, (a) is a legitimate deployment optimization
for a fixed 28-person gate. Either way the **rank-based k-th-error-pair threshold must be re-derived**
for the new distance — thresholds do not transfer across descriptors.

**Expected outcome (literature-based expectation, to be verified on the clean loop):** ≥ LBPH-χ²
accuracy at 1/600th the feature size, passing the < 1 KB budget — i.e., the 6/30 selection no longer has
to trade accuracy against footprint.

### 1b. Zero-code / interim shrinks (do these regardless)

- **Per-identity mean histograms (nearest-centroid LBPH):** store 28 averaged histograms instead of 336
  training histograms → 32 MB → ~2 MB, 12× fewer χ² comparisons. Mean-histogram templates are standard in
  the LBP literature; if the per-pose spread worries us, keep 2–3 k-means centroids per identity.
- **Save OpenCV models as `*.yml.gz`.** `FileStorage` writes YAML *text*; the `.gz` suffix enables
  built-in gzip (typically 3–5× smaller, one-line change, reads transparently).
- **Don't ship the LFW/aug-trained LBPH.** Model size scales with stored histograms (3.79 GB on LFW);
  with the centroid or projection variants this problem disappears by construction.

---

## 2. Patch LBPH's measured failure modes (noise / blur / dark)

Our three worst AR cells map one-to-one onto known LBP weaknesses with named, tested fixes:

- **Gaussian noise (AR 47.8%, heavy 12.5%) → LTP.** LBP thresholds *exactly* at the center-pixel value,
  so uniform regions flip codes under noise. Tan & Triggs' **Local Ternary Patterns** add a ±t dead zone
  (3-valued codes split into two binary maps) specifically to fix this, and pair with the *same
  Tan-Triggs preprocessing chain we already adopted* — it is one coherent, validated system
  ([Tan & Triggs, TIP 2010](https://pubmed.ncbi.nlm.nih.gov/20172829/),
  [Springer AMFG 2007](https://link.springer.com/chapter/10.1007/978-3-540-75690-3_13)).
  Implementation rides on §1's custom extractor (LTP u2 histograms → same LDA).
  Cheap complementary cell for the sweep: 3×3 median / σ≈0.5–1 Gaussian pre-filter, and radius-2
  bilinear-sampled LBP (multiresolution LBP is inherently less noise-sensitive, Ojala 2002).
- **Motion/Gaussian blur (AR 68.5% / 88.1%, heavy 28.6% / 73.2%) → LPQ.** **Local Phase Quantization**
  histograms (Fourier-phase based) are blur-*invariant* under common blur models; Ahonen et al. showed LPQ
  **outperforms LBP on both blurred and sharp faces** on CMU-PIE / FRGC
  ([ICPR 2008](https://ieeexplore.ieee.org/document/4761847/),
  [Ojansivu & Heikkilä](https://www.sciencedirect.com/science/article/abs/pii/S0262885612000510)).
  Same region-histogram-→-LDA pipeline; concatenating LBP+LPQ before LDA is a documented fusion
  ([fast multi-scale LPQ histogram](https://www.sciencedirect.com/science/article/abs/pii/S0167865512001936)).
  Stretch goal — only if the gate environment makes blur a real risk (it does: walking subjects).
- **Brightness-down (AR 73.7%, heavy 39.3%):** suspected interaction of Tan-Triggs' γ=0.2 stage
  amplifying sensor noise in very dark crops. Sweep cells worth one run each: CLAHE→TT stacking, γ=0.3,
  and σ₀/σ₁ DoG variants — all parameters of the existing `tan_triggs_normalize`.

---

## 3. Eigen/Fisher: apply the known fixes once, then stop

Honest framing for the 6/30 selection: at 100 ppm FAR, 23%/11% TAR with EER >30% is a *structural*
failure of pixel-domain holistic subspaces at this FAR; the literature treats them as baselines that
local-texture methods beat by wide margins. Spend one sweep, not a sprint:

- **Distance metric (biggest known Eigen lever):** OpenCV's recognizers hardcode L2. The FERET/CSU
  evaluations established that **Mahalanobis-cosine / whitened-cosine distances dominate Euclidean** for
  PCA spaces — the CSU baseline standardized on MahCosine
  ([Perlibakas, *Distance measures for PCA-based face recognition*](https://www.sciencedirect.com/science/article/abs/pii/S0167865504000248),
  [CSU/FERET distance-measure studies](https://www.researchgate.net/publication/281684384_Effect_of_Distance_Measures_on_the_Performance_of_Face_Recognition_Using_Principal_Component_Analysis)).
  Needs `cv2.PCACompute` + our own distance (small, fits the pipeline package).
- **Drop the first ~3 principal components.** Belhumeur et al. (the Fisherfaces paper itself) showed the
  leading PCs capture illumination variation (Lambertian 3-D lighting subspace) and discarding them
  improves lighting robustness ([TPAMI 1997 PDF](https://cseweb.ucsd.edu/classes/wi14/cse152-a/fisherface-pami97.pdf)) —
  directly relevant to our dark/light split and Eigen's brightness_down weakness.
- **Shrinkage LDA for Fisherfaces** (same Lu et al. citations as §1) — one flag in sklearn.
- **Do NOT chase Tan-Triggs for Eigen/Fisher.** Our sweep already measured it tanking them
  (TAR 19.6%/14.3%); that matches the method's design — TT strips low-frequency content and is built to
  feed LBP/LTP-style features, not pixel subspaces. The sweep behaved exactly as the literature predicts.

If after the §3 sweep Eigen/Fisher still miss (likely), the defensible report narrative is:
*"LDA on pixels (Fisherfaces) fails at the spec FAR; the same LDA on local-texture histograms (§1)
passes"* — Fisherfaces isn't discarded, its machinery is upgraded.

---

## 4. The fps/latency gap is the detector — fix it at the 6/16 detection lock

- **Propose YuNet (`cv2.FaceDetectorYN`) as the locked detector.** ~75 K params / < 1 MB, designed for
  edge CPUs, millisecond-class, and substantially more accurate than Haar (occlusion, side faces, small
  faces, dark frames) — see [OpenCV's official comparison](https://opencv.org/blog/opencv-face-detection-cascade-classifier-vs-yunet/)
  and [an independent eval](https://github.com/TonyCongqianWang/cv_facedetection_eval/). Our DL teammates
  already use it (`yunet_mobilefacenet` artifacts) — converging on it unifies the pipeline.
  Recognizers stay 100% classical; detection is shared infrastructure, and the classical-vs-DL comparison
  is about the *recognizer*. With detection at ~5–10 ms, all three classical models clear 30 fps and the
  < 100 ms latency target with margin.
- **YuNet's 5 landmarks fix alignment for free.** Our clean loop runs `align_eyes=False` because eye-Haar
  is unreliable at 100×100; misalignment is the **dominant documented killer of holistic methods**
  ("curse of mis-alignment": ~5% landmark error → up to 40% recognition drop, eigenfaces most sensitive —
  [Shan et al., ICAFGR 2004](https://ieeexplore.ieee.org/document/1301550/)) and visibly hurts us:
  rotation AR = 26.3% (Eigen) / 14.3% (Fisher) / 83.5% heavy-71.4% (LBPH). Similarity-transform alignment
  from YuNet's eye points (at full-frame resolution, *before* the 100×100 crop) should lift the rotation
  and zoom AR columns for **all three** models and is the only intervention on the list that helps
  Eigen/Fisher's worst modification.
- **If the team insists on Haar-only:** detect on a downscaled frame (`downscale_max_side≈320` — already
  implemented but defaulted off), raise `scaleFactor` to 1.2, detect every N frames with the optical-flow
  ROI tracking that `src/lbph/detect.py` already has (port to the other two). Standard Viola-Jones cost
  controls; gets ~2× fps, but without the landmark/alignment and dark-frame benefits.

---

## 5. Evaluation hygiene that protects the result (cheap, do alongside)

- **56 probes ⇒ 1.8% quantization** on every headline number (the sweep doc says it itself). For the 6/30
  decision, tighten with leave-2-out × 6 folds over the 12 images/identity (336 probes) and report
  binomial (Wilson) intervals. Standard practice; the clean-loop scripts make folds mechanical.
- **Keep the 76 ppm resolvable-FAR floor visible** next to every "@100 ppm" claim (13,149 impostors can't
  express finer than 1/13,149). It's already footnoted — keep it in the paper tables too.
- **Re-derive thresholds per descriptor** via the same rank-based k-th-error-pair procedure whenever the
  feature or distance changes (§1/§2 variants). Never reuse a χ²-scale threshold on an LDA-space cosine.

---

## 6. Priority order vs deadlines

| Deadline | Action | Cost | Expected effect (to verify, not assume) |
|---|---|---|---|
| **6/16 detection lock** | §4 YuNet proposal + landmark alignment contract | team decision + glue code | all models ≥30 fps, <100 ms; rotation/zoom AR up; dark-frame detection up |
| **6/30 selection** | §1b centroid + `.yml.gz` now | hours | LBPH 32 MB → ~2 MB, 12× fewer comparisons |
| **6/30 selection** | §1 u2-LBP(+LTP) → shrinkage-LDA variant through the existing sweep harness | the main build | LBPH-class TAR at 108–800 B feature → **passes <1 KB**; the selection stops being a trade-off |
| **6/30 selection** | §3 Eigen/Fisher one-shot sweep (MahCosine, drop-3-PCs, shrinkage) | small | honest baseline row for the report; retire if still failing |
| **6/30 selection** | §5 folds + intervals | small | defensible numbers at 1.8%→sub-1% granularity |
| **7/15 independence** | re-run rank-based thresholds on the chosen descriptor (§5) | per spec | valid operating point for the new feature space |
| **7/15+ (stretch)** | §2 LPQ / LBP+LPQ fusion cell | medium | blur AR column up (walking-subject robustness) |
| **7/30 hybrid input** | hand the <1 KB projected embedding + threshold to fusion | — | classical signal fuses at DL-embedding cost |

### What this plan deliberately does *not* do

- No deep-learning recognizer creep into the classical track — every recognizer above is a linear
  projection over hand-crafted local texture; YuNet sits in the shared detection stage.
- No further Tan-Triggs experiments on Eigen/Fisher (measured + literature-explained dead end).
- No blind LBPH grid/radius grid-search — the literature locates the gains in descriptor family
  (u2/LTP/LPQ) and projection, not in ±1 radius. One cell for Ahonen's 7×7 u2 reference config is enough.

---

## 7. Source list

- Ahonen, Hadid, Pietikäinen — *Face Recognition with Local Binary Patterns* (ECCV 2004) / *Face
  Description with LBP: Application to Face Recognition* (TPAMI 2006):
  [Semantic Scholar](https://www.semanticscholar.org/paper/Face-Recognition-with-Local-Binary-Patterns-Ahonen-Hadid/32420c65f8ef0c5bd83b14c8ae662cbce73e6781) ·
  [PDF](https://scispace.com/pdf/face-recognition-with-local-binary-patterns-530w9v6pt6.pdf) ·
  [ResearchGate (TPAMI)](https://www.researchgate.net/publication/6690158_Face_Description_with_Local_Binary_Patterns_Application_to_Face_Recognition)
- Ojala, Pietikäinen, Mäenpää — multiresolution / uniform LBP (TPAMI 2002): summarized in
  [Scholarpedia: Local Binary Patterns](http://www.scholarpedia.org/article/Local_Binary_Patterns)
- Chan, Kittler, Messer — *Multi-scale Local Binary Pattern Histograms for Face Recognition* (ICB 2007):
  [Springer](https://link.springer.com/chapter/10.1007/978-3-540-74549-5_85) ·
  [PDF](https://link.springer.com/content/pdf/10.1007/978-3-540-74549-5_85.pdf)
- Tan, Triggs — *Enhanced Local Texture Feature Sets for Face Recognition Under Difficult Lighting
  Conditions* (AMFG 2007 / TIP 2010): [PubMed](https://pubmed.ncbi.nlm.nih.gov/20172829/) ·
  [Springer](https://link.springer.com/chapter/10.1007/978-3-540-75690-3_13)
- Ahonen, Rahtu, Ojansivu, Heikkilä — *Recognition of Blurred Faces Using Local Phase Quantization*
  (ICPR 2008): [IEEE](https://ieeexplore.ieee.org/document/4761847/); Heikkilä et al., *LPQ for
  blur-insensitive image analysis*: [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0262885612000510);
  *Fast multi-scale LPQ histogram for face recognition*:
  [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0167865512001936)
- Perlibakas — *Distance measures for PCA-based face recognition* (PRL 2004):
  [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0167865504000248); CSU/FERET
  distance-measure evaluations:
  [ResearchGate](https://www.researchgate.net/publication/281684384_Effect_of_Distance_Measures_on_the_Performance_of_Face_Recognition_Using_Principal_Component_Analysis)
- Belhumeur, Hespanha, Kriegman — *Eigenfaces vs. Fisherfaces* (TPAMI 1997):
  [PDF](https://cseweb.ucsd.edu/classes/wi14/cse152-a/fisherface-pami97.pdf)
- Lu, Plataniotis, Venetsanopoulos — regularized LDA for small-sample-size face recognition:
  [PRL 2005](https://www.sciencedirect.com/science/article/abs/pii/S0167865504002260) ·
  [PRL 2004](https://www.sciencedirect.com/science/article/abs/pii/S0167865503001673)
- Shan, Chang, Gao, Cao — *Curse of mis-alignment in face recognition* (ICAFGR 2004):
  [IEEE](https://ieeexplore.ieee.org/document/1301550/)
- YuNet vs Haar: [OpenCV official blog](https://opencv.org/blog/opencv-face-detection-cascade-classifier-vs-yunet/) ·
  [independent evaluation repo](https://github.com/TonyCongqianWang/cv_facedetection_eval/)
