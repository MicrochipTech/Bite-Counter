# Meal Monitoring — Architecture

## Dual-Model Inference on Hailo-8

The app runs two neural networks on a single Hailo-8 chip (26 TOPS, PCIe Gen3 x4) using round-robin scheduling. Both models are loaded as separate `HailoInfer` instances that share one virtual device via `group_id = "SHARED"`.

### Hardware Connection

```
Hailo-8 (M.2 M-Key)
    |
Thunderbolt PCIe Enclosure
    |
Thunderbolt 3/4 cable
    |
Windows Laptop --> HailoRT driver --> HailoInfer --> your app
```

Thunderbolt tunnels real PCIe Gen3 x4 lanes — no USB translation, full bandwidth.

### Pipeline

```
USB Camera
    |
    v
preprocess thread --> resize to 640x640 --> input_queue
                                               |
                                               v
                                         infer thread
                                          |-- YOLOv8m (OD)     --> food/utensil bounding boxes
                                          '-- YOLOv8s_pose     --> 17 body keypoints per person
                                               |
                                               v
                                         output_queue (frame, od_result, pose_result)
                                               |
                                               v
                                   post-process callback
                                    |-- extract_detections() --> BYTETracker --> MealState
                                    |-- PoseExtractor --> GestureClassifier --> MealState
                                    '-- DashboardRenderer.render(snapshot)
                                               |
                                               v
                                       [camera feed | dashboard panel] --> OpenCV display
```

### Threading Model

Three threads:
1. **Preprocess** — reads camera frames, resizes to 640x640 for model input
2. **Infer** — runs both models sequentially per frame (OD first, then pose), puts 3-tuple on output queue
3. **Main (visualize)** — dequeues results, runs post-processing callback, renders display

## Object Detection

YOLOv8m detects 80 COCO classes. We filter to meal-relevant subsets:

| Category | COCO Class IDs | Items |
|----------|----------------|-------|
| Food | 46-55 | banana, apple, sandwich, orange, broccoli, carrot, hot dog, pizza, donut, cake |
| Utensils | 42-45, 60 | fork, knife, spoon, bowl, dining table |
| Drinks | 39-41 | bottle, wine glass, cup |

BYTETracker assigns persistent track IDs to prevent double-counting items that briefly disappear between frames.

## Pose Estimation

YOLOv8s_pose outputs 9 tensors across 3 scales. `PoseExtractor` wraps the existing `PoseEstPostProcessing` class for anchor decoding, NMS, and coordinate mapping, producing 17 COCO keypoints per person:

```
 0: Nose           5: L Shoulder    9: L Wrist     13: L Knee
 1: L Eye          6: R Shoulder   10: R Wrist     14: R Knee
 2: R Eye          7: L Elbow      11: L Hip       15: L Ankle
 3: L Ear          8: R Elbow      12: R Hip       16: R Ankle
 4: R Ear
```

Pose model output type MUST be `FLOAT32` for softmax/sigmoid decoding.

## Gesture Classification

The `GestureClassifier` tracks the highest-confidence person over a 30-frame sliding window and evaluates three independent signals each frame:

### Signal 1: Wrist Near Face
Is either wrist within 2.5x head-width of the nose? Checked across the last 5 frames, needs 2+ to fire. Head width is estimated as half the shoulder width (minimum 40px).

### Signal 2: Bent Elbow
Calculates the angle at the elbow joint (shoulder -> elbow -> wrist). Below 130 degrees = bent arm — what happens when bringing food or a drink to the mouth.

### Signal 3: Wrist Above Shoulders
In image coordinates (Y increases downward), wrist Y < shoulder midpoint Y = hand is raised.

### Classification Rules

| Signals met | Drink detected? | Result |
|-------------|-----------------|--------|
| 2+ of 3 | Yes (bottle/cup/glass from OD) | **Drinking** |
| 2+ of 3 | No | **Eating** |
| Raised + bent, not near face | — | **Reaching** |
| Both wrists below shoulders, still 10+ frames | — | **Resting** |

## Performance

| Configuration | FPS | Notes |
|---|---|---|
| Dual model (OD + pose) | ~10-15 | Default mode |
| Single model (`--no-gesture`) | ~20-25 | No gesture detection |

Using YOLOv8**s**_pose (small) instead of medium to keep dual-model FPS reasonable.
