/**
 * Robustness Variants Benchmark Dataset
 * 6 Tracks sorted least to greatest LBPH Clean TAR with combined TAR & (+/-delta%) baseline string.
 */

window.ROBUSTNESS_DATA = {
  version: "0.81.0",
  lastUpdated: "2026-08-02",
  baselineTar: 2.26,

  // Sorted ascending by LBPH Clean TAR/AR (6 tracks)
  tracks: [
    {
      id: "hybrid-identification",
      title: "1. Hybrid LFW2 Identification",
      subtitle: "Wild Single-Shot (5,749 Enrolled, 1,680 Probes)",
      tag: "Baseline (Lowest)",
      summary: "Canonical 1-to-N benchmark evaluating LBPH, SFace, and Cascade across all 41 modifications.",
      lbphCleanVal: 2.26,
      tarCombinedStr: "2.26% (Baseline)",
      isBaseline: true,
      metrics: [
        { label: "LBPH AR (Clean)", value: "2.26%", note: "Lowest baseline TAR" },
        { label: "SFace AR (Clean)", value: "92.02%", note: "DL baseline on wild LFW" },
        { label: "Cascade AR (41-Mod)", value: "80.65%", note: "Matches SFace accuracy" },
        { label: "Escalation Rate", value: "97.51%", note: "Passed to SFace when uncertain" },
        { label: "Isolated Latency", value: "82.54 ms", note: "Faster than SFace-only (84.36ms)" }
      ],
      modesTable: [
        { mode: "LBPH (cv_only)", arClean: "2.26%", ar41Avg: "1.41%", escalation: "—", latency: "72.49 ms" },
        { mode: "SFace (dl_only)", arClean: "92.02%", ar41Avg: "80.65%", escalation: "—", latency: "84.36 ms" },
        { mode: "Cascade (hybrid)", arClean: "92.02%", ar41Avg: "80.65%", escalation: "97.51%", latency: "82.54 ms" }
      ],
      takeaway: "LBPH cannot gate wild LFW probes at 10ppm FAR, causing 97.51% escalation. Cascade maintains 80.65% accuracy while cutting mean latency to 82.54ms.",
      docLink: "docs/experiments/robustness_variants/hybrid-identification/README.md"
    },
    {
      id: "lasalle-db1-identification",
      title: "2. La Salle DB1 (1 Gallery Image)",
      subtitle: "Single-Photo Enrollment Isolation (28 Enrolled, 11 Probes)",
      tag: "Single-Shot Test",
      summary: "Isolates the effect of single-photo enrollment on controlled dataset.",
      lbphCleanVal: 8.44,
      tarCombinedStr: "8.44% (+6.18%)",
      isBaseline: false,
      metrics: [
        { label: "LBPH AR (Clean)", value: "8.44%", note: "Single-photo enrollment" },
        { label: "Delta vs Baseline", value: "+6.18%", note: "Absolute TAR gain over baseline" },
        { label: "SFace AR (Clean)", value: "99.35%", note: "SFace baseline accuracy" },
        { label: "Cascade AR (41-Mod)", value: "98.70%", note: "Recovers via SFace" },
        { label: "Escalation Rate", value: "91.60%", note: "Escalates almost all probes" }
      ],
      modesTable: [
        { mode: "LBPH (cv_only)", arClean: "8.44%", ar41Avg: "5.12%", escalation: "—", latency: "71.50 ms" },
        { mode: "SFace (dl_only)", arClean: "99.35%", ar41Avg: "98.70%", escalation: "—", latency: "84.20 ms" },
        { mode: "Cascade (hybrid)", arClean: "99.35%", ar41Avg: "98.70%", escalation: "91.60%", latency: "83.10 ms" }
      ],
      takeaway: "Single-photo enrollment causes sharp LBPH drop (8.44% vs 92.86% multi-photo), proving photo volume per person is primary limitation.",
      docLink: "docs/experiments/robustness_variants/lasalle-db1-identification/README.md"
    },
    {
      id: "lfw-multishot-lbph",
      title: "3. LFW Multi-shot LBPH",
      subtitle: "Multi-Photo Enrollment on Wild Data (~10 Training Photos / Person)",
      tag: "Scaling Test",
      summary: "Tests whether multi-photo enrollment on wild LFW images improves LBPH.",
      lbphCleanVal: 21.85,
      tarCombinedStr: "21.85% (+19.59%)",
      isBaseline: false,
      metrics: [
        { label: "LBPH AR (Clean)", value: "21.85%", note: "9.7x gain over single-photo" },
        { label: "Delta vs Baseline", value: "+19.59%", note: "Absolute TAR gain over baseline" },
        { label: "SFace AR (Clean)", value: "92.02%", note: "Reference DL accuracy" },
        { label: "Target FAR Target", value: "10 ppm", note: "Strict deployment threshold" }
      ],
      modesTable: [
        { mode: "LBPH (Single-shot)", arClean: "2.26%", ar41Avg: "1.41%", escalation: "—", latency: "72.49 ms" },
        { mode: "LBPH (Multi-shot ~10x)", arClean: "21.85%", ar41Avg: "14.20%", escalation: "—", latency: "73.10 ms" },
        { mode: "SFace (dl_only)", arClean: "92.02%", ar41Avg: "80.65%", escalation: "—", latency: "84.36 ms" }
      ],
      takeaway: "Multi-shot training yields a 9.7x boost for LBPH (+19.59% absolute), but 21.85% remains too low for 10ppm FAR requirements.",
      docLink: "docs/experiments/robustness_variants/lfw-multishot-lbph/README.md"
    },
    {
      id: "pairwise-verification",
      title: "4. Pairwise Verification (10% FAR Sweep)",
      subtitle: "Loosened FAR Checkpoint (10% FAR Target)",
      tag: "Threshold Sweep",
      summary: "Evaluates whether loosening FAR target from 10ppm to 10% can recover LBPH TAR.",
      lbphCleanVal: 31.25,
      tarCombinedStr: "31.25% (+28.99%)",
      isBaseline: false,
      metrics: [
        { label: "10% FAR TAR (Clean)", value: "31.25%", note: "tau = 79.52" },
        { label: "Delta vs Baseline", value: "+28.99%", note: "Absolute TAR gain over 10ppm" },
        { label: "10 ppm Deployed TAR", value: "2.26%", note: "Baseline operating point" },
        { label: "EER Checkpoint", value: "60.71%", note: "Unbound reference" }
      ],
      modesTable: [
        { mode: "10 ppm FAR (Deployed)", arClean: "2.26%", ar41Avg: "1.43%", escalation: "97.5%", latency: "67.03 threshold" },
        { mode: "100 ppm FAR", arClean: "3.87%", ar41Avg: "2.36%", escalation: "95.1%", latency: "68.88 threshold" },
        { mode: "1% FAR", arClean: "14.11%", ar41Avg: "9.23%", escalation: "82.4%", latency: "74.35 threshold" },
        { mode: "10% FAR Checkpoint", arClean: "31.25%", ar41Avg: "23.30%", escalation: "59.8%", latency: "79.52 threshold" }
      ],
      takeaway: "Giving up FAR almost entirely (to 10%) only raises clean TAR to 31.25% (+28.99% absolute). Chi-square LBPH native distributions overlap on wild LFW.",
      docLink: "docs/experiments/robustness_variants/pairwise-verification/lfw-results/README.md"
    },
    {
      id: "att-faces-identification",
      title: "5. AT&T Faces Identification",
      subtitle: "Controlled Environment (40 Identities, Uniform Pose/Lighting)",
      tag: "Controlled Test",
      summary: "Tests LBPH under strictly controlled environment conditions.",
      lbphCleanVal: 38.75,
      tarCombinedStr: "38.75% (+36.49%)",
      isBaseline: false,
      metrics: [
        { label: "LBPH AR (Clean)", value: "38.75%", note: "17x higher than wild LFW" },
        { label: "Delta vs Baseline", value: "+36.49%", note: "Absolute TAR gain from control" },
        { label: "SFace AR (Clean)", value: "100.00%", note: "Flawless on controlled gallery" },
        { label: "Cascade AR (41-Mod)", value: "99.88%", note: "Near perfect overall" }
      ],
      modesTable: [
        { mode: "LBPH (cv_only)", arClean: "38.75%", ar41Avg: "38.31%", escalation: "—", latency: "68.10 ms" },
        { mode: "SFace (dl_only)", arClean: "100.00%", ar41Avg: "99.88%", escalation: "—", latency: "83.10 ms" },
        { mode: "Cascade (hybrid)", arClean: "100.00%", ar41Avg: "99.88%", escalation: "61.20%", latency: "74.80 ms" }
      ],
      takeaway: "LBPH jumps from 2.26% to 38.75% (+36.49% absolute) under controlled lighting, proving classical algorithm is functioning correctly but requires low-variation images.",
      docLink: "docs/experiments/robustness_variants/att-faces-identification/README.md"
    },
    {
      id: "lasalle-db1-identification-clean10",
      title: "6. La Salle DB1 (10 Gallery Images)",
      subtitle: "Optimal 10-Gallery Recipe (28 Enrolled: 5 Light + 5 Dark Poses)",
      tag: "Optimal Recipe",
      summary: "Evaluates LBPH with optimal multi-pose and multi-lighting enrollment photos per person.",
      lbphCleanVal: 92.86,
      tarCombinedStr: "92.86% (+90.60%)",
      isBaseline: false,
      metrics: [
        { label: "LBPH AR (Clean)", value: "92.86%", note: "Multi-pose enrollment" },
        { label: "Delta vs Baseline", value: "+90.60%", note: "Maximum observed TAR gain" },
        { label: "SFace AR (Clean)", value: "100.00%", note: "Perfect baseline accuracy" },
        { label: "Cascade AR (41-Mod)", value: "99.65%", note: "Near perfect overall" }
      ],
      modesTable: [
        { mode: "LBPH (cv_only)", arClean: "92.86%", ar41Avg: "84.12%", escalation: "—", latency: "70.20 ms" },
        { mode: "SFace (dl_only)", arClean: "100.00%", ar41Avg: "99.65%", escalation: "—", latency: "84.00 ms" },
        { mode: "Cascade (hybrid)", arClean: "100.00%", ar41Avg: "99.65%", escalation: "15.80%", latency: "72.40 ms" }
      ],
      takeaway: "Multi-photo enrollment enables LBPH to achieve 92.86% AR (+90.60% absolute over baseline) and drops cascade escalation to 15.8%.",
      docLink: "docs/experiments/robustness_variants/lasalle-db1-identification-clean10/README.md"
    }
  ],

  farSweepData: [
    { targetFar: "10 ppm (Deployed)", tau: 67.0333, cleanTar: 2.26, overallTar: 1.43, escalationPct: 97.51, estLatency: 82.54 },
    { targetFar: "100 ppm", tau: 68.8808, cleanTar: 3.87, overallTar: 2.36, escalationPct: 95.10, estLatency: 81.80 },
    { targetFar: "0.1% (1,000 ppm)", tau: 71.1718, cleanTar: 7.08, overallTar: 4.33, escalationPct: 91.20, estLatency: 79.50 },
    { targetFar: "1%", tau: 74.3496, cleanTar: 14.11, overallTar: 9.23, escalationPct: 82.40, estLatency: 75.30 },
    { targetFar: "5%", tau: 77.5943, cleanTar: 23.99, overallTar: 17.26, escalationPct: 70.10, estLatency: 69.80 },
    { targetFar: "10%", tau: 79.5150, cleanTar: 31.25, overallTar: 23.30, escalationPct: 59.80, estLatency: 64.20 },
    { targetFar: "EER (Reference)", tau: 85.7090, cleanTar: 60.71, overallTar: 57.67, escalationPct: 38.20, estLatency: 53.10 }
  ],

  modificationsData: [
    { family: "Brightness Change", tier: "Light (+10%)", lbph: "85.2%", sface: "98.5%", cascade: "98.5%", icon: "☀️" },
    { family: "Brightness Change", tier: "Medium (+30%)", lbph: "84.1%", sface: "97.8%", cascade: "97.8%", icon: "☀️" },
    { family: "Brightness Change", tier: "Heavy (-50% Dark)", lbph: "73.7%", sface: "96.2%", cascade: "96.2%", icon: "🌙" },
    { family: "Gaussian Blur", tier: "Light (3x3)", lbph: "82.4%", sface: "96.8%", cascade: "96.8%", icon: "💧" },
    { family: "Gaussian Blur", tier: "Medium (5x5)", lbph: "68.5%", sface: "95.1%", cascade: "95.1%", icon: "💧" },
    { family: "Gaussian Blur", tier: "Heavy (9x9)", lbph: "49.2%", sface: "91.3%", cascade: "91.3%", icon: "💧" },
    { family: "Gaussian Noise", tier: "Light (sigma=5)", lbph: "71.0%", sface: "94.2%", cascade: "94.2%", icon: "⚡" },
    { family: "Gaussian Noise", tier: "Medium (sigma=15)", lbph: "58.3%", sface: "88.9%", cascade: "88.9%", icon: "⚡" },
    { family: "Gaussian Noise", tier: "Heavy (sigma=30)", lbph: "47.8%", sface: "74.1%", cascade: "74.1%", icon: "⚡" },
    { family: "Rotation", tier: "Light (5°)", lbph: "84.9%", sface: "97.9%", cascade: "97.9%", icon: "🔄" },
    { family: "Rotation", tier: "Medium (15°)", lbph: "79.2%", sface: "95.4%", cascade: "95.4%", icon: "🔄" },
    { family: "Rotation", tier: "Heavy (45°)", lbph: "38.1%", sface: "82.6%", cascade: "82.6%", icon: "🔄" },
    { family: "Contrast Adjustment", tier: "Light (1.2x)", lbph: "85.0%", sface: "98.1%", cascade: "98.1%", icon: "🎨" },
    { family: "Contrast Adjustment", tier: "Medium (1.5x)", lbph: "83.6%", sface: "97.2%", cascade: "97.2%", icon: "🎨" },
    { family: "Contrast Adjustment", tier: "Heavy (0.5x)", lbph: "76.4%", sface: "95.0%", cascade: "95.0%", icon: "🎨" },
    { family: "Scale / Resize", tier: "Light (0.8x)", lbph: "84.8%", sface: "98.0%", cascade: "98.0%", icon: "🔍" },
    { family: "Scale / Resize", tier: "Medium (0.5x)", lbph: "78.2%", sface: "96.1%", cascade: "96.1%", icon: "🔍" },
    { family: "Scale / Resize", tier: "Heavy (0.25x)", lbph: "52.4%", sface: "89.5%", cascade: "89.5%", icon: "🔍" }
  ]
};
