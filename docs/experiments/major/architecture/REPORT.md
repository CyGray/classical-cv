# Full Evaluation Report: Quality-First Early-Bypass Routing (La Salle DB1-DL41)

> **Scope: Full 2,296 Transformed Conditions (56 held-out test images x 41 DL41 transforms)**  
> **Timing Protocol**: 1 warmup pass + 5 timed repetitions with per-probe randomized execution order.

## 1. Executive Summary & Equivalence Confirmation

- **Total Transformed Conditions**: `2296`
- **YuNet Face Detector Failures**: `107` (4.66%)
- **Invariant Assertions**:
  - Final decision mismatches between Sequential Cascade & Early-Bypass: **0 / 2,296** (100.00% exact match)
  - SFace routing mismatches between Sequential Cascade & Early-Bypass: **0 / 2,296** (100.00% exact match)
  - LBPH calls eliminated by early bypass: **994 / 2,296** (43.29%)

## 2. Accuracy Comparison

| Mode | Correct Acceptance (TPIR) | Correct Rate (%) | SFace Invocations | LBPH Invocations | Dual Inferences |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Always LBPH** | 704 / 2296 | 30.66% | 0 (0.0%) | 2189 (95.34%) | 0 (0.0%) |
| **Direct SFace** | 2030 / 2296 | 88.41% | 2189 (95.34%) | 0 (0.0%) | 0 (0.0%) |
| **Current Cascade (Seq)** | 2030 / 2296 | 88.41% | 1782 (77.61%) | 2189 (95.34%) | 1782 (77.61%) |
| **Quality-Only Router** | 1355 / 2296 | 59.02% | 994 (43.29%) | 1195 (52.05%) | 0 (0.0%) |
| **Quality-First Early Bypass** | 2030 / 2296 | 88.41% | 1782 (77.61%) | 1195 (52.05%) | 788 (34.32%) |

## 3. Recognition-Stage Latency (Excluding Face Detection)

| Mode | Mean Latency (ms) | Median / p50 (ms) | p95 (ms) |
| :--- | :--- | :--- | :--- |
| **Always LBPH** | 4.733 ms | 4.632 ms | 5.490 ms |
| **Direct SFace** | 8.623 ms | 8.444 ms | 9.952 ms |
| **Current Cascade (Seq)** | 11.955 ms | 13.113 ms | 15.298 ms |
| **Quality-Only Router** | 6.684 ms | 5.398 ms | 9.715 ms |
| **Quality-First Early Bypass** | 9.771 ms | 9.041 ms | 14.269 ms |

### Latency Savings:
- **Mean Latency Reduction**: `2.184 ms` (18.27% faster)
- **LBPH Invocations Avoided**: `994 / 2,296` (43.29%)

### Branch Latency Breakdown (Early Bypass):
- **Branch 1: Quality-Triggered -> SFace**: `994` conditions (8.869 ms mean, 8.69 ms p50)
- **Branch 2: Quality-Clear -> LBPH Terminal**: `407` conditions (4.811 ms mean, 4.68 ms p50)
- **Branch 3: Quality-Clear -> Dual (LBPH + SFace)**: `788` conditions (13.469 ms mean, 13.189 ms p50)

## 4. Quality Diagnostic Contingency Table

```text
                     LBPH Correct    LBPH Failure    Total
Quality Clear        415             780             1195
Quality Flagged      289             705             994
Total                704             1485            2189
```

- **Recall of LBPH Failures by Quality Flags**: `47.47%` (705 / 1485)
- **False Alarm (Unnecessary Quality Flag on LBPH Correct)**: `41.05%` (289 / 704)
