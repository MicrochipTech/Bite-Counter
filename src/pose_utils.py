import sys
from pathlib import Path
import numpy as np

_repo_root = Path(__file__).resolve().parents[1]
_pose_dirs = [
    _repo_root / "deps" / "hailo-apps" / "hailo_apps" / "python" / "standalone_apps" / "pose_estimation",
    _repo_root / "pose_estimation",
]
for _d in _pose_dirs:
    if _d.exists():
        sys.path.insert(0, str(_d))
        break

from pose_estimation_utils import PoseEstPostProcessing


class PoseExtractor:
    def __init__(self):
        self.processor = PoseEstPostProcessing(
            max_detections=300,
            score_threshold=0.001,
            nms_iou_thresh=0.7,
            regression_length=15,
            strides=[8, 16, 32],
        )

    def extract(
        self,
        raw_results: dict,
        model_h: int,
        model_w: int,
        frame_h: int,
        frame_w: int,
        detection_threshold: float = 0.5,
        joint_threshold: float = 0.3,
    ) -> list[dict]:
        results = self.processor.post_process(raw_results, model_h, model_w, class_num=1)

        bboxes = results["bboxes"][0]
        keypoints = results["keypoints"][0]
        joint_scores = results["joint_scores"][0]
        scores = results["scores"][0]

        persons = []
        for i in range(len(scores)):
            if scores[i] < detection_threshold:
                continue

            kpts = keypoints[i].reshape(17, 2).copy()
            kpts = self.processor.map_keypoints_to_original_coords(
                kpts, frame_w, frame_h, model_w, model_h
            )

            bbox = self.processor.map_box_to_original_coords(
                bboxes[i].tolist(), frame_w, frame_h, model_w, model_h
            )

            j_scores = joint_scores[i].flatten()

            persons.append({
                "keypoints": kpts,
                "joint_scores": j_scores,
                "bbox": bbox,
                "score": float(scores[i].item()),
            })

        return persons
