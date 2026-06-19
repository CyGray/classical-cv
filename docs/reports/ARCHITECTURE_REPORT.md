# LS-Face — Hybrid CV + DL Architecture (Report)

*The short, visual version. Full detail lives in [`ARCHITECTURE_PLAN.md`](ARCHITECTURE_PLAN.md).*

**Goal:** combine our classical recognizer (LBPH) with the DL recognizer (SFace)
into one system that is **fast like CV** and **accurate like DL**, running on a
Raspberry Pi 5.

---

## 1. The idea in one picture

```
        ┌──────────────┐         ┌──────────────────────────┐
        │   CV (LBPH)  │         │   DL (YuNet + SFace)     │
        │  fast, cheap │   +     │  robust, accurate        │
        │  weak on hard│         │  heavier to compute      │
        │  inputs      │         │                          │
        └──────┬───────┘         └────────────┬─────────────┘
               │                              │
               └────────────► HYBRID ◄────────┘
                                │
                "Let CV do the easy cases.
                 Call DL only for the hard ones."
```

We don't pick one. **CV handles the easy faces; DL rescues the hard ones.**

---

## 2. What each side is good at

| | **CV — LBPH** | **DL — SFace** |
|---|---|---|
| Speed | ✅ fast on CPU | ⚠️ heavy (needs accelerator) |
| Clean frontal face | ✅ 100% | ✅ 100% |
| Blur / noise / low light | ❌ weak | ✅ robust |
| Off-pose | ❌ weak | ✅ robust |
| Feature size (<1 KB target) | ❌ 64 KB | ✅ 512 B |

> **They're opposites.** Each one's weakness is the other's strength — that's why
> a hybrid beats either alone.

---

## 3. How they combine — the gated cascade

One shared front-end (YuNet) feeds CV first. A **gate** decides if DL is needed.

```
   camera frame
        │
        ▼
  ┌───────────────────────────┐
  │  YuNet: detect + align    │   ← shared by both, gives box + 5 landmarks
  └─────────────┬─────────────┘
                ▼
  ┌───────────────────────────┐
  │  LBPH (CV)  — runs on CPU  │   ← cheap, every frame
  └─────────────┬─────────────┘
                ▼
            ╔═══════╗
            ║ GATE  ║   "Is CV sure, and is the image clean?"
            ╚═══╤═══╝
       YES ◄────┴────► NO
        │              │
        ▼              ▼
   ┌─────────┐   ┌──────────────────────┐
   │ Accept  │   │  SFace (DL) — on NPU │   ← only the hard cases
   │ on CV   │   │  final decision      │
   └─────────┘   └──────────┬───────────┘
                            ▼
                    ┌───────────────┐
                    │ Identity / ❌ │
                    └───────────────┘
```

**Most frames are clean → they stop at CV → the system stays fast.**
DL only wakes up for the few hard frames.

---

## 4. The gate — when do we switch to DL?

Switch to SFace if **any** of these is true:

```
   ┌─ CV unsure?  ──────────────► score near the match/no-match line
   │
   │─ Two people tied? ─────────► top-1 and top-2 too close
   │
   │─ Image blurry? ────────────► \
   │─ Too dark? ────────────────►  } the exact things CV is bad at
   │─ Noisy? ───────────────────► /
   │─ Face turned / too small? ─►/
   │
   └─► ESCALATE TO DL
```

Otherwise → trust CV (fast path). The blur/dark/noise checks are cheap and reuse
what YuNet already gives us (face score, landmarks, size).

---

## 5. Professor's suggestion #1 — DL covers CV's weak spots

We measured *exactly* where LBPH fails. DL is sent in for those cases:

```
   LBPH weak spot        →   gate trigger   →   DL handles it
   ─────────────────────────────────────────────────────────
   Gaussian noise  47.8% ─┐
   Motion blur     68.5% ─┤
   Brightness down 73.7% ─┼──►  quality probe  ──►  SFace
   Off-pose              ─┤
   Near-threshold guess  ─┘
```

This is the suggestion turned into a rule: **DL runs only where CV is proven weak.**

---

## 6. Professor's suggestion #2 — Raspberry Pi accelerator

**Problem:** the rich DL feature (SFace CNN, 37.8 MB) is too slow on the Pi CPU
to run every frame.
**Fix:** don't shrink the feature — move it to a neural accelerator (NPU).

```
   Raspberry Pi 5
   ┌────────────────────────┐        ┌────────────────────────┐
   │  CPU                    │        │  NPU  (Hailo / Coral)  │
   │  • LBPH (fast path)     │  ⇄     │  • YuNet  (every frame)│
   │  • the gate + checks    │        │  • SFace  (hard cases) │
   │  • gallery match        │        │    runs as INT8        │
   └────────────────────────┘        └────────────────────────┘
        light work on CPU                heavy CNN on the NPU
```

- YuNet + SFace are ONNX → they compile onto the NPU.
- LBPH stays on the CPU (it's cheap).
- Result: the heavy feature is **fast** because the NPU does it, so we can keep
  **≥30 fps** on-device. No accelerator? → fall back to CV-only.

---

## 7. Why this works (the whole report in 3 lines)

```
   CV is fast but weak on hard images.     ─┐
   DL is robust but heavy.                  ─┼─►  Use CV by default,
   The NPU makes DL cheap when we need it.  ─┘    call DL only when needed.
```

We get CV's **speed**, DL's **accuracy**, and DL's **tiny 512-byte feature** —
all at once, instead of trading one for another.

---

## 8. What we need to build (checklist)

```
   [ ] 1. Copy YuNet weights into the CV repo (detector already supports it)
   [ ] 2. Wrap SFace so it plugs in like LBPH (same interface)
   [ ] 3. Build the gate (CV → decide → maybe DL)
   [ ] 4. Calibrate thresholds with the independence test + measure fused accuracy
   [ ] 5. Add a "Hybrid" option to main.py
   [ ] 6. Put YuNet + SFace (INT8) on the Pi's accelerator
```

> Note: the combined accuracy number is a **projection** until step 4 is actually
> run. We report it as measured only after that.
