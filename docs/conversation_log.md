# Meal Monitoring Dashboard — Development Log

**Date:** 2026-09-29  
**Developer:** Gokce (Microchip FAE, Hailo Advocate)

---

## Session Overview

This session continued from a prior conversation where the dual-model meal monitoring app was built and running. Three topics were covered:

1. Fixing the gesture classifier (Drinking not detected)
2. Full architecture walkthrough
3. Creating a setup skill for coworker handoff

---

## 1. Gesture Classifier Fix

### Problem

The gesture classifier showed **"Resting (50%)"** when the user was clearly drinking from a bottle with a bent elbow and wrist at face level. The bottle was detected at 82% confidence, but the gesture wasn't triggered.

### Root Causes

| Issue | Old Value | Problem |
|-------|-----------|---------|
| Wrist-to-nose threshold | `1.5x` head width (~120px) | Too tight — wrist near mouth isn't necessarily near nose |
| Min eating frames | 5 out of 5 | At ~10 FPS dual-model, requires 0.5s of perfect alignment |
| Head width base | `shoulder_width * 0.4` | Underestimates, creating too-small threshold |
| Elbow angle | Not tracked | User's bent elbow was a clear signal being ignored |
| Wrist height | Not checked | Raised hand is an obvious eating indicator |

### Solution — Signal Voting

Rewrote `gesture_classifier.py` with three independent signals:

**Signal 1 — Wrist near face:** Either wrist within `2.5x` head width of nose, checked over last 5 frames, needs only 2 to fire.

**Signal 2 — Bent elbow:** Calculates shoulder-elbow-wrist angle. Angle < 130 degrees = bent arm.

```python
def _angle_at_joint(a, joint, b):
    v1 = a - joint
    v2 = b - joint
    cos = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-6)
    return np.degrees(np.arccos(np.clip(cos, -1.0, 1.0)))
```

**Signal 3 — Wrist above shoulders:** In image coordinates (Y increases downward), wrist Y < shoulder midpoint Y means hand is raised.

**Classification logic:** Any 2 of 3 signals triggers Eating. If a drink (bottle/cup/glass) is also detected by the OD model, it becomes Drinking.

### Key Parameter Changes

| Parameter | Old | New |
|-----------|-----|-----|
| `WRIST_NOSE_RATIO` | 1.5 | 2.5 |
| `MIN_EATING_FRAMES` | 5 | 2 |
| `MIN_RESTING_FRAMES` | 15 | 10 |
| `head_width` multiplier | 0.4 | 0.5 |
| `head_width` minimum | 30px | 40px |
| `JOINT_CONFIDENCE_THRESHOLD` | 0.3 | 0.25 |
| `ELBOW_ANGLE_THRESHOLD` | N/A | 130.0 |
| Elbow keypoints tracked | No | Yes (indices 7, 8) |

---

## 2. Architecture Walkthrough

### Hardware

- **Hailo-8**: M.2 M-Key AI accelerator, 26 TOPS, PCIe Gen3 x4
- **Connection**: Thunderbolt PCIe enclosure → Thunderbolt 3/4 cable → laptop
- Thunderbolt tunnels real PCIe lanes — no USB translation, full bandwidth

### Dual-Model Inference

Two models run on the same Hailo-8 chip via round-robin scheduling:

| Model | Task | Output |
|-------|------|--------|
| YOLOv8m (medium) | Object detection | Bounding boxes + 80 COCO classes |
| YOLOv8s_pose (small) | Pose estimation | 17 body keypoints per person |

Shared via `HailoInfer` with `group_id = "SHARED"` and `ROUND_ROBIN` scheduling. Combined throughput: ~10-15 FPS.

### Pipeline Flow

```
USB Camera
    |
    v
preprocess thread --> resize to 640x640 --> input_queue
                                               |
                                               v
                                         infer thread
                                          |-- YOLOv8m     -> food/utensil boxes
                                          '-- YOLOv8s_pose -> 17 keypoints
                                               |
                                               v
                                         output_queue (frame, od_result, pose_result)
                                               |
                                               v
                                   post-process callback
                                    |-- extract_detections() -> BYTETracker -> meal_state
                                    |-- PoseExtractor -> GestureClassifier -> meal_state
                                    '-- DashboardRenderer.render(snapshot)
                                               |
                                               v
                                       [camera feed | dashboard] -> display
```

### Object Detection Filtering

- **Food**: COCO classes 46-55 (banana, apple, sandwich, orange, broccoli, carrot, hot dog, pizza, donut, cake)
- **Utensils**: classes 39-45, 60 (bottle, wine glass, cup, fork, knife, spoon, bowl, dining table)
- **Drink subset**: classes 39-41 (bottle, wine glass, cup) — triggers `drink_near_wrist` flag

### Pose Keypoints (COCO 17)

```
 0: Nose           5: L Shoulder    9: L Wrist     13: L Knee
 1: L Eye          6: R Shoulder   10: R Wrist     14: R Knee
 2: R Eye          7: L Elbow      11: L Hip       15: L Ankle
 3: L Ear          8: R Elbow      12: R Hip       16: R Ankle
 4: R Ear
```

Pose model output type MUST be `FLOAT32` for softmax/sigmoid decoding in post-processing.

### Gesture Classification Summary

| Gesture | Condition |
|---------|-----------|
| **Eating** | 2+ signals: wrist near face, bent elbow, or raised wrist |
| **Drinking** | Eating signals + bottle/cup/glass detected by OD model |
| **Reaching** | Wrist raised + bent elbow, but not near face |
| **Resting** | Both wrists below shoulders, still for 10+ frames |

### File Structure

```
meal_monitoring/
├── meal_monitoring.py              # Main entry, dual HailoInfer, CLI args
├── meal_monitoring_post_process.py # OD + pose processing, skeleton drawing
├── meal_state.py                   # Food/utensil/gesture tracking, events
├── dashboard_renderer.py           # OpenCV side panel rendering
├── gesture_classifier.py           # 3-signal heuristic classifier
├── pose_utils.py                   # PoseExtractor (wraps pose_estimation decoder)
└── config.json                     # Score threshold (0.35), tracker buffer (45)
```

### Thunderbolt vs Raspberry Pi

| | Thunderbolt (this setup) | Raspberry Pi + AI HAT+ |
|---|---|---|
| Host | Windows laptop | Raspberry Pi 5 |
| Connection | PCIe over Thunderbolt | PCIe over FPC ribbon |
| Driver | HailoRT for Windows | HailoRT for Linux |
| Performance | Full PCIe Gen3 x4 | PCIe Gen2 x1 |
| Portability | Laptop + enclosure | Compact single-board |

---

## 3. Setup Skill for Coworker Handoff

Created `.hailo/skills/hl-setup-meal-monitoring.md` — a step-by-step guide covering:

1. Prerequisites (Windows, Thunderbolt, webcam, Python 3.10+, Git)
2. HailoRT installation (Windows installer + Python wheel from Developer Zone)
3. Repo clone, venv setup, pip install
4. Environment variables (`HAILO_ARCH`, `PYTHONPATH`)
5. Model download (auto or manual)
6. Run command with all flags explained
7. Verification checklist (10 items)
8. Troubleshooting table (7 common issues)

Registered in `.hailo/README.md` (Setup Skills category) and `CLAUDE.md` (skills table).

Invoke with: `/hl-setup-meal-monitoring`

---

## Run Command

```cmd
cd hailo_apps\python\standalone_apps\meal_monitoring
python meal_monitoring.py -n yolov8m -i usb --show-fps
```

| Flag | Purpose |
|------|---------|
| `-n yolov8m` | Object detection model |
| `-i usb` | USB webcam input |
| `--show-fps` | Display frame rate |
| `--pose-model yolov8s_pose` | Pose model (default) |
| `--no-gesture` | Single-model mode (~25 FPS) |
| `--dashboard-width 400` | Dashboard width in pixels |
