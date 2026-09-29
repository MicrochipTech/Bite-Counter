import cv2
import numpy as np
from types import SimpleNamespace

try:
    from hailo_apps.python.core.common.toolbox import id_to_color
except ImportError:
    from pathlib import Path
    import sys
    core_dir = Path(__file__).resolve().parents[2] / "core"
    sys.path.insert(0, str(core_dir))
    from common.toolbox import id_to_color

from hailo_apps.python.standalone_apps.object_detection.object_detection_post_process import (
    extract_detections,
)

FOOD_CLASS_IDS = {46, 47, 48, 49, 50, 51, 52, 53, 54, 55}
UTENSIL_CLASS_IDS = {39, 40, 41, 42, 43, 44, 45, 60}
DRINK_CLASS_IDS = {39, 40, 41}
MEAL_CLASS_IDS = FOOD_CLASS_IDS | UTENSIL_CLASS_IDS


def draw_meal_detection(image, box, label, score, color):
    xmin, ymin, xmax, ymax = map(int, box)
    cv2.rectangle(image, (xmin, ymin), (xmax, ymax), color, 2)
    text = f"{label}: {score:.0f}%"
    cv2.putText(image, text, (xmin + 4, ymin + 20), cv2.FONT_HERSHEY_SIMPLEX,
                0.5, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.putText(image, text, (xmin + 4, ymin + 20), cv2.FONT_HERSHEY_SIMPLEX,
                0.5, (255, 255, 255), 1, cv2.LINE_AA)


def draw_skeleton(image, persons, joint_threshold=0.3):
    JOINT_PAIRS = [
        (0, 1), (1, 3), (0, 2), (2, 4),
        (5, 6), (5, 7), (7, 9), (6, 8), (8, 10),
        (5, 11), (6, 12), (11, 12),
        (11, 13), (12, 14), (13, 15), (14, 16),
    ]
    for person in persons:
        kpts = person["keypoints"]
        scores = person["joint_scores"]
        for j0, j1 in JOINT_PAIRS:
            if scores[j0] > joint_threshold and scores[j1] > joint_threshold:
                pt1 = (int(kpts[j0][0]), int(kpts[j0][1]))
                pt2 = (int(kpts[j1][0]), int(kpts[j1][1]))
                cv2.line(image, pt1, pt2, (255, 0, 255), 2)
        for i, (kp, sc) in enumerate(zip(kpts, scores)):
            if sc > joint_threshold:
                cv2.circle(image, (int(kp[0]), int(kp[1])), 3, (0, 255, 255), -1)


def meal_inference_result_handler(original_frame, infer_results, pose_results=None,
                                  labels=None, config_data=None,
                                  tracker=None, meal_state=None, dashboard_renderer=None,
                                  pose_extractor=None, gesture_classifier=None,
                                  pose_model_h=640, pose_model_w=640):
    detections = extract_detections(original_frame, infer_results, config_data)

    boxes = detections["detection_boxes"]
    scores = detections["detection_scores"]
    classes = detections["detection_classes"]
    num = detections["num_detections"]

    meal_indices = [i for i in range(num) if classes[i] in MEAL_CLASS_IDS]

    food_dets = []
    utensil_dets = []
    drink_near_wrist = False

    if meal_indices:
        dets_for_tracker = []
        det_class_map = []
        for i in meal_indices:
            dets_for_tracker.append([*boxes[i], scores[i]])
            det_class_map.append(classes[i])

        online_targets = tracker.update(np.array(dets_for_tracker))

        for track in online_targets:
            track_id = track.track_id
            x1, y1, x2, y2 = track.tlbr
            box = [int(x1), int(y1), int(x2), int(y2)]

            best_idx = _find_best_match(track.tlbr, [d[:4] for d in dets_for_tracker])
            if best_idx is None:
                continue

            cls_id = det_class_map[best_idx]
            label = labels[cls_id]
            score = track.score
            color = tuple(id_to_color(cls_id).tolist())

            draw_meal_detection(original_frame, box, label, score * 100, color)

            entry = {"track_id": track_id, "label": label, "score": score}
            if cls_id in FOOD_CLASS_IDS:
                food_dets.append(entry)
            else:
                utensil_dets.append(entry)
                if cls_id in DRINK_CLASS_IDS:
                    drink_near_wrist = True
    else:
        tracker.update(np.empty((0, 5)))

    meal_state.update(food_dets, utensil_dets)

    if pose_results is not None and pose_extractor is not None and gesture_classifier is not None:
        frame_h, frame_w = original_frame.shape[:2]
        persons = pose_extractor.extract(
            pose_results, pose_model_h, pose_model_w, frame_h, frame_w
        )

        if persons:
            draw_skeleton(original_frame, persons)
            gesture, confidence = gesture_classifier.update(persons, food_near_wrist=drink_near_wrist)
            meal_state.update_gesture(gesture, confidence, source="camera")
        else:
            gesture, confidence = gesture_classifier.update([], food_near_wrist=False)

    snapshot = meal_state.get_snapshot()
    dashboard = dashboard_renderer.render(snapshot)
    dashboard = cv2.resize(dashboard, (dashboard.shape[1], original_frame.shape[0]))
    return np.hstack([original_frame, dashboard])


def _find_best_match(track_box, detection_boxes):
    best_iou = 0
    best_idx = None
    for i, det_box in enumerate(detection_boxes):
        xa = max(track_box[0], det_box[0])
        ya = max(track_box[1], det_box[1])
        xb = min(track_box[2], det_box[2])
        yb = min(track_box[3], det_box[3])
        inter = max(0, xb - xa) * max(0, yb - ya)
        area_a = max(1e-5, (track_box[2] - track_box[0]) * (track_box[3] - track_box[1]))
        area_b = max(1e-5, (det_box[2] - det_box[0]) * (det_box[3] - det_box[1]))
        iou = inter / (area_a + area_b - inter + 1e-5)
        if iou > best_iou:
            best_iou = iou
            best_idx = i
    return best_idx
