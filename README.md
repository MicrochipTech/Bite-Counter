# Meal Monitoring Dashboard

Real-time meal monitoring using dual AI models on the **Hailo-8** accelerator. Detects food, utensils, and drinks with YOLOv8m while simultaneously tracking body pose with YOLOv8s_pose to classify eating gestures — all running on a single chip via round-robin scheduling.

Built for Windows laptops with Hailo-8 connected through a Thunderbolt PCIe enclosure.

<!-- TODO: Add screenshot of the dashboard in action -->

## Hardware Requirements

| Component | Details |
|---|---|
| **Hailo-8** | M.2 M-Key AI accelerator module (26 TOPS) |
| **Thunderbolt enclosure** | M.2 to Thunderbolt PCIe enclosure |
| **Laptop** | Windows 10/11 with Thunderbolt 3 or 4 port |
| **Webcam** | USB or integrated webcam |

## Quick Start

### Step 1: Install HailoRT

Download from the [Hailo Developer Zone](https://hailo.ai/developer-zone/) (Software Downloads > HailoRT > Windows):

1. Run **HailoRT Windows installer** (`HailoRT-X.XX.X-win64.exe`) — installs PCIe driver + runtime
2. Download the **HailoRT Python wheel** (`hailort-X.XX.X-cpXXX-win_amd64.whl`) — you'll install this in Step 2

Verify the device is detected:

```cmd
hailortcli fw-control identify
```

### Step 2: Run Setup

```cmd
git clone https://github.com/MicrochipTech/meal-monitoring.git
cd meal-monitoring
setup.bat
```

Then install the HailoRT Python wheel into the venv:

```cmd
venv\Scripts\activate
pip install path\to\hailort-4.23.0-cp310-cp310-win_amd64.whl
```

### Step 3: Run

```cmd
run.bat
```

Or manually:

```cmd
venv\Scripts\activate
set PYTHONPATH=deps\hailo-apps
set HAILO_ARCH=hailo8
python src\meal_monitoring.py -n yolov8m -i usb --show-fps
```

AI models download automatically on first run (~40 MB total).

## What You'll See

The app opens a window with two panels:

**Left — Camera Feed:**
- Bounding boxes around food, utensils, and drinks (color-coded)
- Skeleton overlay on detected person (magenta lines, yellow keypoints)

**Right — Dashboard:**
- Meal duration timer
- Detected food items with confidence scores
- Detected utensils/drinks with confidence scores
- Current gesture: **Eating** / **Drinking** / **Reaching** / **Resting**
- Event log with timestamps

Press **Q** or **Esc** to quit.

## Command Line Options

| Flag | Default | Description |
|------|---------|-------------|
| `-n` | `yolov8m` | Object detection model |
| `-i` | — | Input source (`usb` for webcam, or video file path) |
| `--show-fps` | off | Display frame rate in terminal |
| `--pose-model` | `yolov8s_pose` | Pose estimation model |
| `--no-gesture` | off | Disable pose model for higher FPS (~25 vs ~12) |
| `--dashboard-width` | `400` | Dashboard panel width in pixels |

## Architecture

Two neural networks share the Hailo-8 chip via a single virtual device with round-robin scheduling:

```
USB Camera --> preprocess --> [YOLOv8m]      --> food/utensil detections --> BYTETracker
                          --> [YOLOv8s_pose] --> 17 body keypoints      --> GestureClassifier
                                                                              |
                                                                              v
                                                          MealState + DashboardRenderer --> Display
```

### Object Detection (YOLOv8m)

Filters COCO detections to meal-relevant classes:
- **Food:** banana, apple, sandwich, orange, broccoli, carrot, hot dog, pizza, donut, cake (classes 46-55)
- **Utensils:** fork, knife, spoon, bowl, dining table (classes 42-45, 60)
- **Drinks:** bottle, wine glass, cup (classes 39-41)

### Gesture Classification (3-Signal Voting)

The classifier tracks body keypoints over a 30-frame sliding window and evaluates three signals per frame:

| Signal | What it checks |
|--------|---------------|
| **Wrist near face** | Either wrist within 2.5x head-width of nose (2+ of last 5 frames) |
| **Bent elbow** | Shoulder-elbow-wrist angle < 130 degrees |
| **Raised wrist** | Either wrist above shoulder level |

Any 2 of 3 signals = **Eating**. If a drink (bottle/cup/glass) is also detected = **Drinking**.

### File Overview

| File | Purpose |
|------|---------|
| `src/meal_monitoring.py` | Main entry point — dual HailoInfer setup, CLI args, inference thread |
| `src/meal_monitoring_post_process.py` | Post-processing callback — OD filtering, skeleton drawing, gesture integration |
| `src/meal_state.py` | State tracker — food items, utensils, gesture, event log |
| `src/dashboard_renderer.py` | OpenCV-rendered side panel |
| `src/gesture_classifier.py` | 3-signal heuristic classifier |
| `src/pose_utils.py` | Wraps PoseEstPostProcessing from hailo-apps pose estimation |
| `config.json` | Score threshold (0.35), tracker buffer (45) |

## Verification Checklist

- [ ] `hailortcli fw-control identify` shows the Hailo-8 device
- [ ] App starts without import errors
- [ ] Log shows `Found HEF in resources: ...yolov8m.hef`
- [ ] Log shows `Loading pose model: ...yolov8s_pose.hef`
- [ ] Camera feed shows bounding boxes on food/utensils
- [ ] Skeleton drawn on detected person
- [ ] Place a bottle in frame — appears under Utensils on dashboard
- [ ] Raise hand to mouth — gesture changes to Eating or Drinking
- [ ] Combined FPS: ~10-15 (shown in terminal with `--show-fps`)

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `No Hailo device found` | Check enclosure power, authorize Thunderbolt in Windows Settings, reconnect cable |
| Camera doesn't open | Close other apps using webcam (Teams, Zoom). Try `-i 1` for alternate camera |
| `ModuleNotFoundError: hailo_platform` | Activate venv, reinstall the HailoRT `.whl` |
| `ModuleNotFoundError: hailo_apps` | Check `PYTHONPATH` points to `deps\hailo-apps`, or re-run `setup.bat` |
| Models not downloading | Check internet. Manually place `.hef` files in `C:\usr\local\hailo\resources\models\hailo8\` |
| Gesture stuck on Resting | Ensure pose model loaded (check logs). Move hand clearly to face with bent elbow |
| Very low FPS (< 5) | Close other apps. Verify Thunderbolt connection (not USB fallback). Try `--no-gesture` |

## License

This project uses the [hailo-apps](https://github.com/hailo-ai/hailo-apps) framework. See its repository for license terms.
