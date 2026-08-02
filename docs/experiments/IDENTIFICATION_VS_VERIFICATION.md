# 1-to-N Open-Set Identification vs. 1:1 Pairwise Verification Protocol

**Date:** 2026-08-01  
**Scope:** Evaluation Protocol Definitions & Standalone LBPH Benchmark Context  
**Target Audience:** USLS CV Group 3 / LS-Face Smart Gate Project

---

## 1. Executive Summary

When evaluating face recognition models on public benchmarks like LFW (Labeled Faces in the Wild), performance numbers depend heavily on the **evaluation protocol**. Confusion between **1-to-N Open-Set Identification** (our Smart Gate deployment baseline) and **1:1 Pairwise Verification** (standard classical publication benchmark) accounts for the discrepancy between LBPH's **~1.74% AR** on the robustness test and **65–75% Accuracy** reported in classical literature.

---

## 2. Protocol Comparison Matrix

| Property | 1:1 Pairwise Verification | 1-to-N Closed-Set Identification | 1-to-N Open-Set Identification (Robustness Test) |
|---|---|---|---|
| **Core Question** | "Do Image A and Image B belong to the same person?" | "Which identity in gallery $G$ ($N$ candidates) does probe $P$ belong to?" | "Is probe $P$ enrolled in gallery $G$? If yes, who is it?" |
| **Gallery Constraint** | No gallery; pairwise matching only. | Probe identity **must** exist in gallery $G$. | Probe identity **may or may not** exist in gallery $G$. |
| **Comparisons per Probe** | 1 comparison ($O(1)$) | $N$ comparisons ($O(N)$) | $N$ comparisons ($O(N)$) |
| **Decision Rule** | $d(A, B) \le \tau \rightarrow \text{Match}$ | $\hat{y} = \arg\min_{i \in G} d(P, G_i)$ | $\min_{i \in G} d(P, G_i) \le \tau_{\text{accept}} \rightarrow \text{Accept } \hat{y}$, else $\text{Reject}$ |
| **Threshold Regime** | Swept ROC curve / EER optimal cutoff ($\tau \approx 76\text{--}78$) | None (takes closest match regardless of distance) | **Strict deployment edge** ($\tau_{\text{accept}} = 67.0084$, $\sim 10\text{ ppm}$ FAR) |
| **Primary Metrics** | Accuracy, EER, TAR @ 1% FAR | Rank-1 Accuracy, Rank-5 Accuracy | True Positive Identification Rate (TPIR / AR @ Thr), FPIR |
| **Real-World Context** | Passport check, phone unlock ($1:1$ claim verification) | Closed system lookup (e.g. employee lookup among enrolled staff) | **Smart Turnstile / Gate** (walk up without card; gate checks 575 users) |
| **Standalone LBPH Outcome** | **65% – 75% Verification Accuracy** | **8.72% Rank-1 Identification** | **1.74% AR @ 67.0084** (Clean LFW2) |

---

## 3. Protocol Deep Dive

### 3.1 1:1 Pairwise Verification Protocol
* **Standard Benchmark Setup:** 6,000 specified image pairs (3,000 genuine same-person pairs, 3,000 impostor different-person pairs across 10 folds).
* **Distance Distribution:** Impostors yield high LBPH distances (median $\approx 85\text{--}95+$); genuine pairs yield lower distances (median $\approx 70\text{--}73$).
* **Separability:** At binary decision boundary ($\tau \approx 76\text{--}78$), LBPH separates genuine vs impostor distributions with **65%–75% accuracy**, matching published classical baselines (Ahonen et al., 2006).

### 3.2 1-to-N Closed-Set Identification
* **Gallery Setup:** Gallery contains $N=575$ enrolled identities. Probes are guaranteed to be in gallery.
* **Result:** LBPH achieves **8.72% Rank-1 accuracy** on clean LFW2. The correct identity is top rank in 15 out of 172 probes.

### 3.3 1-to-N Open-Set Identification (Operational Gate Baseline)
* **Operational Requirement:** Gate must deny entry to un-enrolled intruders while accepting enrolled students. False positive rate across $N=575$ comparisons must be $\le 10\text{ ppm}$.
* **Threshold Constraint:** Requires strict cutoff `tau_accept = 67.0084` (native `predict_collect` scale).
* **Domain Shift Impact:** On unconstrained, in-the-wild LFW faces, lighting, pose, and background shift median genuine LBPH distance to **`69.12`**.
* **Consequence:** Strict threshold `67.0084` rejects $80\%$ of LBPH's correct Rank-1 identifications, yielding **`1.74%` AR**.

---

## 4. Reporting & Thesis Guidelines

1. **For Smart Gate Deployment & Cascade Justification:**
   - Report **`1.74%` AR @ 67.0084** for 1-to-N Open-Set Identification.
   - Explains why classical histogram matching alone fails on unconstrained wild faces and proves necessity of SFace deep cascade escalation.

2. **For Published Classical Baseline Comparison:**
   - Report **`65% – 75%` Verification Accuracy** on standard LFW 1:1 6,000-pair protocol.
   - Provides apples-to-apples comparison against classical literature without penalizing LBPH for 10 ppm 1-to-N gate threshold constraints.
