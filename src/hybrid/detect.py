"""Live hybrid detection: the gated cascade on a webcam.

Reuses the LBPH live scaffold (``src/lbph/detect.py``) - YuNet detect every N
frames, optical-flow tracking in between, temporal voting to stabilise the name -
but swaps ``recognizer.predict()`` for ``HybridRecognizer.predict()`` and draws
the **deciding engine** + **escalated** flag on the overlay so the CV->DL hand-off
is visible on screen.

The per-run FPS summary is written with ``algorithm="hybrid"`` into the same
``reports/benchmark/live_fps/runs/`` directory the FPS aggregator
(``src/benchmark/aggregate_live_fps.py``) reads, so the launcher's benchmark
overview picks up the hybrid's average FPS automatically.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter, deque
from datetime import datetime, timezone
from pathlib import Path

import cv2 as cv
import numpy as np

from src.classical_faces.detection import create_face_detector
from src.hybrid.recognizer import (
    DEFAULT_LBPH_LABELS,
    DEFAULT_LBPH_MODEL,
    DEFAULT_SFACE_GALLERY,
    DEFAULT_THRESHOLDS_PATH,
    HYBRID_MODES,
    build_hybrid,
    make_sample,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def root_path(*parts: str) -> str:
    return str(PROJECT_ROOT.joinpath(*parts))


def resolve_path(value: str) -> str:
    p = Path(value)
    return str(p) if p.is_absolute() else str(PROJECT_ROOT / p)


def iou(box_a, box_b) -> float:
    ax, ay, aw, ah = box_a
    bx, by, bw, bh = box_b
    x1, y1 = max(ax, bx), max(ay, by)
    x2, y2 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    if inter == 0:
        return 0.0
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def clamp_box(box, width: int, height: int):
    x, y, w, h = box
    x = max(0, min(int(x), width - 1))
    y = max(0, min(int(y), height - 1))
    w = max(1, min(int(w), width - x))
    h = max(1, min(int(h), height - y))
    return x, y, w, h


def box_to_points(box):
    x, y, w, h = box
    return np.array([[[x, y]], [[x + w, y]], [[x + w, y + h]], [[x, y + h]]], dtype="float32")


def points_to_box(points, width: int, height: int):
    pts = points.reshape(-1, 2)
    x_min = int(max(0, min(pts[:, 0])))
    y_min = int(max(0, min(pts[:, 1])))
    x_max = int(min(width - 1, max(pts[:, 0])))
    y_max = int(min(height - 1, max(pts[:, 1])))
    return clamp_box((x_min, y_min, max(1, x_max - x_min), max(1, y_max - y_min)), width, height)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Live hybrid (LBPH + SFace) face recognition.")
    p.add_argument(
        "--mode",
        choices=list(HYBRID_MODES),
        default="cascade",
        help="cascade (default), parallel, cv_only (no-accelerator fallback), dl_only.",
    )
    p.add_argument("--thresholds-path", default=DEFAULT_THRESHOLDS_PATH)
    p.add_argument("--lbph-model", default=DEFAULT_LBPH_MODEL)
    p.add_argument("--lbph-labels", default=DEFAULT_LBPH_LABELS)
    p.add_argument("--sface-gallery", default=DEFAULT_SFACE_GALLERY)
    p.add_argument("--camera-index", type=int, default=0)
    p.add_argument("--downscale-max-side", type=int, default=640)
    p.add_argument("--min-face-size", type=int, default=72)
    p.add_argument("--detect-every", type=int, default=3, help="Full YuNet detection every N frames.")
    p.add_argument("--track-between-detections", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--temporal-window", type=int, default=5)
    p.add_argument("--min-stable-hits", type=int, default=3)
    p.add_argument("--min-stable-frames", type=int, default=2)
    p.add_argument("--yunet-score-threshold", type=float, default=0.6)
    p.add_argument("--yunet-nms-threshold", type=float, default=0.3)
    p.add_argument("--fps-summary-dir", default=root_path("reports", "benchmark", "live_fps", "runs"))
    p.add_argument("--fps-log-path", default=root_path("reports", "benchmark", "live_fps", "hybrid_fps.jsonl"))
    p.add_argument("--fps-log-interval", type=float, default=1.0)
    p.add_argument("--session-log-json", default="")
    p.add_argument("--disable-fps-log", action="store_true")
    return p.parse_args()


def _engine_color(name: str, engine: str) -> tuple[int, int, int]:
    if name == "Unknown":
        return (0, 0, 255)          # red
    if engine == "sface":
        return (0, 200, 255)        # amber: DL escalation decided
    return (0, 255, 0)              # green: LBPH fast path decided


def main() -> None:
    args = parse_args()
    args.fps_summary_dir = resolve_path(args.fps_summary_dir)
    args.fps_log_path = resolve_path(args.fps_log_path)
    if args.session_log_json:
        args.session_log_json = resolve_path(args.session_log_json)

    cv.setUseOptimized(True)

    detector = create_face_detector(
        "yunet",
        min_face_size=args.min_face_size,
        downscale_max_side=args.downscale_max_side,
        yunet_score_threshold=args.yunet_score_threshold,
        yunet_nms_threshold=args.yunet_nms_threshold,
    )
    hybrid = build_hybrid(
        mode=args.mode,
        thresholds_path=resolve_path(args.thresholds_path),
        lbph_model=resolve_path(args.lbph_model),
        lbph_labels=resolve_path(args.lbph_labels),
        sface_gallery=resolve_path(args.sface_gallery),
        require_sface=(args.mode != "cv_only"),
    )
    print(f"[INFO] Detector: {detector.describe()}")
    print(f"[INFO] Hybrid mode: {hybrid.mode} | identities: {len(hybrid.labels)}")
    print("[INFO] Press 'd' to exit.")

    webcam = cv.VideoCapture(args.camera_index)
    if not webcam.isOpened():
        raise RuntimeError(f"Could not open webcam index {args.camera_index}")

    detect_every = max(1, args.detect_every)
    temporal_window = max(1, args.temporal_window)
    min_stable_hits = max(1, min(args.min_stable_hits, temporal_window))
    min_stable_frames = max(1, args.min_stable_frames)

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    fps_log_interval = max(0.2, args.fps_log_interval)
    fps_log_file = None
    if not args.disable_fps_log:
        Path(args.fps_log_path).parent.mkdir(parents=True, exist_ok=True)
        fps_log_file = Path(args.fps_log_path).open("a", encoding="utf-8")

    run_started = time.time()
    last_log_time = 0.0
    frame_count = detection_count = recognition_count = track_updates = 0
    escalation_count = 0
    engine_usage = {"lbph": 0, "sface": 0}
    fps_sum = 0.0
    fps_samples = 0

    previous_frame_time = time.time()
    fps_ema = 0.0
    rec_fps_ema = 0.0
    rec_tick_last = time.time()
    rec_tick_count = 0

    prediction_history: deque[tuple[str, bool]] = deque(maxlen=temporal_window)
    tracked_box = None
    track_points = None
    stable_frames = 0
    prev_gray = None

    current_label = "Unknown"
    current_engine = "lbph"
    current_escalated = False
    current_detail = ""

    while True:
        ret, frame = webcam.read()
        if not ret:
            break
        frame_count += 1
        now = time.time()
        delta = now - previous_frame_time
        previous_frame_time = now
        fps = (1.0 / delta) if delta > 0 else 0.0
        fps_ema = fps if fps_ema == 0.0 else 0.85 * fps_ema + 0.15 * fps
        if fps > 0:
            fps_sum += fps
            fps_samples += 1

        gray = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)
        h, w = gray.shape[:2]

        # --- optical-flow tracking between detector passes ----------------- #
        updated_by_tracking = False
        if (
            args.track_between_detections
            and tracked_box is not None
            and track_points is not None
            and prev_gray is not None
            and (frame_count % detect_every) != 0
        ):
            next_points, status, _ = cv.calcOpticalFlowPyrLK(prev_gray, gray, track_points, None)
            if next_points is not None and status is not None:
                good_new = next_points[status.flatten() == 1]
                if len(good_new) >= 3:
                    new_box = points_to_box(good_new.reshape(-1, 1, 2), w, h)
                    if iou(tracked_box, new_box) > 0.05:
                        tracked_box = new_box
                        track_points = good_new.reshape(-1, 1, 2).astype("float32")
                        stable_frames += 1
                        updated_by_tracking = True
                        track_updates += 1

        # --- detection (carries box + landmarks for SFace alignCrop) ------- #
        current_detection = None
        need_detect = (frame_count % detect_every == 0) or (tracked_box is None)
        if need_detect and not updated_by_tracking:
            detections = detector.detect(gray, frame)
            detection_count += 1
            if not detections:
                tracked_box = None
                track_points = None
                prediction_history.clear()
                stable_frames = 0
                current_label = "Unknown"
                current_detail = ""
            else:
                current_detection = max(detections, key=lambda d: d.area)
                tracked_box = clamp_box(current_detection.box, w, h)
                track_points = box_to_points(tracked_box)
                stable_frames = 1

        # --- recognise on every fresh detection ---------------------------- #
        # Detection-driven (not tracked_box-driven like the LBPH loop): SFace
        # needs the fresh YuNet landmarks for alignCrop, which only a real
        # detection carries. Display stability comes from the temporal voting
        # below (min_stable_hits), so we must NOT also gate on stable_frames -
        # detection resets it to 1, which would block recognition forever.
        if current_detection is not None:
            sample = make_sample(
                current_detection, image_bgr=frame, image_gray=gray, assume_cropped=False
            )
            decision = hybrid.predict(sample)
            engine_usage[decision.engine] = engine_usage.get(decision.engine, 0) + 1
            if decision.escalated:
                escalation_count += 1
            recognition_count += 1
            rec_tick_count += 1

            prediction_history.append((decision.name, decision.escalated))
            stable_hits = [n for n, _ in prediction_history if n != "Unknown"]
            if stable_hits:
                top_name, top_count = Counter(stable_hits).most_common(1)[0]
                if top_count >= min_stable_hits:
                    current_label = top_name
                else:
                    current_label = "Unknown"
            else:
                current_label = "Unknown"
            current_engine = decision.engine
            current_escalated = decision.escalated
            if decision.engine == "sface" and decision.sface_cosine is not None:
                current_detail = f"cos={decision.sface_cosine:.2f}"
            else:
                current_detail = f"d={decision.lbph_distance:.1f}"

            if (now - rec_tick_last) >= 1.0:
                recent_rec_fps = rec_tick_count / max(1e-6, now - rec_tick_last)
                rec_fps_ema = (
                    recent_rec_fps if rec_fps_ema == 0.0 else 0.80 * rec_fps_ema + 0.20 * recent_rec_fps
                )
                rec_tick_last = now
                rec_tick_count = 0

        # --- overlay ------------------------------------------------------- #
        if tracked_box is not None:
            x, y, fw, fh = clamp_box(tracked_box, w, h)
            color = _engine_color(current_label, current_engine)
            cv.rectangle(frame, (x, y), (x + fw, y + fh), color, 2)
            engine_tag = "SFACE*" if current_escalated else current_engine.upper()
            cv.putText(
                frame,
                f"{current_label} [{engine_tag}] {current_detail}",
                (x, max(0, y - 10)),
                cv.FONT_HERSHEY_COMPLEX, 0.55, (255, 255, 255), 2, cv.LINE_AA,
            )

        esc_rate = (100.0 * escalation_count / recognition_count) if recognition_count else 0.0
        cv.putText(
            frame,
            f"FPS {fps_ema:.1f} | RecFPS {rec_fps_ema:.1f} | mode {hybrid.mode}",
            (10, 30), cv.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2,
        )
        cv.putText(
            frame,
            f"Escalation {esc_rate:.0f}% | LBPH {engine_usage['lbph']} | SFace {engine_usage['sface']}",
            (10, 58), cv.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2,
        )

        elapsed_seconds = now - run_started
        if fps_log_file is not None and (elapsed_seconds - last_log_time) >= fps_log_interval:
            fps_log_file.write(json.dumps({
                "run_id": run_id, "algorithm": "hybrid", "mode": hybrid.mode,
                "elapsed_seconds": elapsed_seconds, "frame_count": frame_count,
                "fps": fps_ema, "recognition_fps": rec_fps_ema,
                "escalation_rate_percent": esc_rate,
            }) + "\n")
            fps_log_file.flush()
            last_log_time = elapsed_seconds

        cv.imshow("Hybrid (LBPH + SFace)", frame)
        prev_gray = gray
        if cv.waitKey(1) & 0xFF == ord("d"):
            break

    webcam.release()
    cv.destroyAllWindows()

    total_seconds = max(0.0, time.time() - run_started)
    avg_fps = (fps_sum / fps_samples) if fps_samples else 0.0
    avg_rec_fps = (recognition_count / total_seconds) if total_seconds > 0 else 0.0
    esc_rate = (100.0 * escalation_count / recognition_count) if recognition_count else 0.0

    Path(args.fps_summary_dir).mkdir(parents=True, exist_ok=True)
    summary_path = Path(args.fps_summary_dir) / f"hybrid_{run_id}.json"
    summary_payload = {
        "run_id": run_id,
        "algorithm": "hybrid",
        "mode": hybrid.mode,
        "detector": "yunet",
        "average_fps": avg_fps,
        "average_recognition_fps": avg_rec_fps,
        "frames": frame_count,
        "detections": detection_count,
        "recognitions": recognition_count,
        "escalations": escalation_count,
        "escalation_rate_percent": esc_rate,
        "engine_usage": engine_usage,
        "tracking_updates": track_updates,
        "duration_seconds": total_seconds,
        "detect_every": detect_every,
        "downscale_max_side": args.downscale_max_side,
    }
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary_payload, f, indent=2)
    if args.session_log_json:
        Path(args.session_log_json).parent.mkdir(parents=True, exist_ok=True)
        with open(args.session_log_json, "w", encoding="utf-8") as f:
            json.dump(summary_payload, f, indent=2)
    if fps_log_file is not None:
        fps_log_file.close()

    print(f"[FPS] Average FPS: {avg_fps:.2f}")
    print(f"[FPS] Average recognition FPS: {avg_rec_fps:.2f}")
    print(f"[FPS] Escalation rate: {esc_rate:.2f}% | engine usage: {engine_usage}")
    print(f"[FPS] Summary: {summary_path}")


if __name__ == "__main__":
    main()
