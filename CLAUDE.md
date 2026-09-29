# Bite-Counter — Meal Monitoring Dashboard

Dual-model Hailo-8 app: YOLOv8m (food/utensil detection) + YOLOv8s_pose (gesture classification) running on Windows via Thunderbolt PCIe enclosure.

## Quick Reference

```cmd
setup.bat          :: First-time setup (clone hailo-apps, create venv, install)
run.bat            :: Launch the app
```

## Skills

| Command | Description |
|---------|-------------|
| `/setup` | Walk through first-time setup on a new Windows machine |

## Project Structure

```
src/                        :: All application source code
  meal_monitoring.py        :: Main entry — dual HailoInfer, CLI args, inference thread
  meal_monitoring_post_process.py :: Post-processing — OD filtering, skeleton, gesture
  meal_state.py             :: State tracker — food, utensils, gesture, events
  dashboard_renderer.py     :: OpenCV dashboard panel
  gesture_classifier.py     :: 3-signal heuristic (wrist proximity, elbow angle, wrist height)
  pose_utils.py             :: Wraps PoseEstPostProcessing from hailo-apps
config.json                 :: Score threshold (0.35), tracker buffer (45)
deps/hailo-apps/            :: hailo-apps framework (cloned by setup.bat, gitignored)
```

## Key Dependencies

- **hailo-apps** framework (cloned into `deps/` by `setup.bat`) — provides HailoInfer, BYTETracker, toolbox, pose utilities
- **hailo_platform** Python wheel — HailoRT bindings, installed separately from Hailo Developer Zone
- **HailoRT Windows installer** — PCIe driver + runtime, from Hailo Developer Zone

## Architecture

Two models share one Hailo-8 chip via `group_id = "SHARED"` with round-robin scheduling:
- **YOLOv8m** — object detection (food classes 46-55, utensil classes 39-45/60, drink classes 39-41)
- **YOLOv8s_pose** — pose estimation (17 COCO keypoints, FLOAT32 output required)

Gesture classifier uses 3-signal voting: wrist-to-face proximity, elbow angle < 130 deg, wrist above shoulders. Any 2/3 = Eating; + drink detected = Drinking.

## Important Notes

- All Python imports use `hailo_apps.python.*` absolute paths — `PYTHONPATH` must point to `deps/hailo-apps`
- Pose model output MUST use `output_type="FLOAT32"` for correct post-processing
- HEF models auto-download on first run to `C:\usr\local\hailo\resources\models\hailo8\`
- `--no-gesture` flag disables pose model for ~2x FPS
