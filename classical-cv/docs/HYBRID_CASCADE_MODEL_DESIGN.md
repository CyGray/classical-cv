# LS-Face: Hybrid Cascade Model Design Document

**Authors:** Computer Vision Research Group 3 (USLS)  
**Project:** Smart Gate Face Recognition System  
**Target Platform:** Edge Hardware (Raspberry Pi 5 with Optional Accelerator)  

The **LS-Face Hybrid Cascade Model** routes every frame through a fast classical
recognizer (**LBPH**) first, and escalates only the frames that need it to a deep
recognizer (**SFace**). This document specifies the pipeline stages, the escalation
gate that decides when to escalate, the tunable thresholds, and the target hardware
layout.

---

## 1. System Architecture and Pipeline Stages

The pipeline has three stages: **shared detection/alignment (YuNet)**, **Stage 1 (classical fast path: LBPH)**, and **Stage 2 (deep escalation: SFace)**.

![LS-Face Hybrid Cascade Model Workflow Diagram](docs/figures/fig_hybrid_system_flow.png)

### 1.1 Front-End Detector (YuNet)
Before face recognition happens, a lightweight neural detector called **YuNet** inspects the raw camera frame.
* **Face Detection:** Locates faces and extracts bounding box coordinates.
* **Facial Keypoint Landmark Alignment:** Identifies 5 key facial points (left eye, right eye, nose tip, left mouth corner, right mouth corner).
* **Shared Efficiency:** YuNet outputs are shared by both recognizers, avoiding duplicate face detection operations.

### 1.2 Stage 1: Classical Fast Path (LBPH Recognizer)
The detected face crop is sent directly to the **LBPH** (Local Binary Patterns Histograms) recognizer on the CPU.
* **Feature Extraction:** Analyzes local texture patterns across small regions of the face.
* **Nearest Neighbor Matching:** Calculates the distance score to enrolled identities. A smaller distance score indicates higher similarity.
* **Relative Margin Check:** Compares the distance score of the top match against the second closest match to confirm clear separation.

### 1.3 Stage 2: Deep Feature Escalation (SFace Recognizer)
When the Escalation Gate determines that a face probe needs deeper inspection, execution moves to **SFace**.
* **Landmark-Based Alignment:** Uses the 5 facial keypoints from YuNet to warp and orient the face crop into a clean, standardized format.
* **Deep Feature Extraction:** Converts the aligned face into a 128-element feature vector representing unique facial characteristics.
* **Similarity Matching:** Measures similarity using Cosine similarity and Euclidean distance against enrolled gallery feature vectors.

---

## 2. The Escalation Gate and Quality Probes

The **Escalation Gate** acts as the intelligent controller of the system. It determines whether LBPH's decision is confident enough to accept, or if SFace must take over.

![Escalation Gate Decision Logic Flowchart](docs/figures/fig_hybrid_gate_flow.png)

### 2.1 Escalation Rules

The gate evaluates three rules in order, and escalates to SFace on the first match:

| # | Rule | Trigger | Rationale |
| :--- | :--- | :--- | :--- |
| 1 | Quality Flag Override | Any quality probe fails (blur, light, noise, pose, size) | Quality checks take priority, as LBPH is unreliable in poor conditions |
| 2 | Ambiguous Distance Band | `tau_accept < distance < tau_reject` | LBPH's own score is inconclusive |
| 3 | Thin Separation Margin | `margin < margin_min` | Top-1 and top-2 matches are a near-tie |

If none of the rules trigger, the gate resolves the frame on the fast path alone:
* `distance <= tau_accept` → **Confident Accept**
* `distance >= tau_reject` → **Confident Reject** (unknown person)

### 2.2 Real-Time Quality Probes

Five lightweight quality probes run during the fast path to check image clarity:

* **Motion Blur Probe:** Measures image sharpness using variance of Laplacian. Images below the blur threshold are marked as blurry.
* **Illumination Probe:** Measures average image brightness (luma). Images below the low-light threshold or above the bright-light threshold are marked as poorly lit.
* **Noise Probe:** Estimates high-frequency sensor noise. Images above the noise threshold are marked as noisy.
* **Off-Pose Angle Probe:** Uses facial landmark locations to check head tilt and turn angle. Faces turned beyond the pose threshold are marked as off-pose.
* **Face Size Probe:** Checks the pixel height and width of the face bounding box. Faces smaller than the size threshold are marked as small faces.

![Quality Probe Distributions and Threshold Edges](docs/figures/fig_hybrid_quality_probes.png)

---

## 3. System Thresholds and Configurations

The hybrid model uses calibrated thresholds to control gate routing and matching decisions.

| Parameter | Function | Scope and Purpose |
| :--- | :--- | :--- |
| **`tau_accept`** | LBPH Accept Distance | Distance score threshold for confident fast path acceptance |
| **`tau_reject`** | LBPH Reject Distance | Distance score threshold for non-enrolled unknown rejection |
| **`margin_min`** | Top-1 vs Top-2 Separation | Minimum relative gap required between best and second-best match |
| **`sface.l2_genuine`** | SFace Matching Distance | Maximum Euclidean distance for genuine deep feature verification |
| **`sface.cosine_genuine`** | SFace Similarity Floor | Minimum Cosine similarity score for genuine deep feature verification |
| **`tau_blur`** | Blur Threshold | Minimum required sharpness value before triggering blur flag |
| **`luma_lo` / `luma_hi`** | Light Range | Acceptable brightness range before triggering illumination flag |
| **`tau_noise`** | Noise Threshold | Maximum tolerable noise level before triggering noise flag |
| **`tau_pose`** | Pose Angle Limit | Maximum head tilt/turn angle before triggering off-pose flag |
| **`px_min`** | Minimum Face Size | Minimum bounding box size required for classical processing |

---

## 4. Edge Hardware and Software Architecture

### 4.1 Deployment on Edge Platforms
The system is tailored for single-board computers like the Raspberry Pi 5.

![Edge Hardware Deployment Architecture](docs/figures/fig_hybrid_hardware_diagram.png)

* **Host CPU (ARM Cortex-A76):** Manages video capture, YuNet preprocessing, LBPH fast path execution, real-time quality probing, and gate control logic.
* **Accelerator / NPU (Optional):** Runs YuNet face detection and SFace deep feature extraction efficiently when available.

### 4.2 Operating Modes and Fallback Protection
The system supports three software operating modes:
* **Cascade Mode (Default):** Full hybrid operation with dynamic quality checking and score gating.
* **CV-Only Mode (Fallback):** Runs purely on LBPH. If deep learning models or neural runtime libraries are missing, the system falls back gracefully to CPU-only operation without crashing.
* **DL-Only Mode (Comparison):** Bypasses LBPH and runs deep feature extraction on every frame for baseline testing.
