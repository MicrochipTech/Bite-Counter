import numpy as np
from collections import deque

NOSE = 0
LEFT_SHOULDER = 5
RIGHT_SHOULDER = 6
LEFT_ELBOW = 7
RIGHT_ELBOW = 8
LEFT_WRIST = 9
RIGHT_WRIST = 10

MIN_EATING_FRAMES = 2
MIN_RESTING_FRAMES = 10
WRIST_NOSE_RATIO = 2.5
ELBOW_ANGLE_THRESHOLD = 130.0
JOINT_CONFIDENCE_THRESHOLD = 0.25


def _angle_at_joint(a: np.ndarray, joint: np.ndarray, b: np.ndarray) -> float:
    v1 = a - joint
    v2 = b - joint
    cos = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-6)
    return np.degrees(np.arccos(np.clip(cos, -1.0, 1.0)))


class GestureClassifier:
    def __init__(self, window_size: int = 30):
        self.window_size = window_size
        self.history: dict[int, deque] = {}
        self.current_gesture = "Resting"
        self.current_confidence = 0.0

    def update(self, persons: list[dict], food_near_wrist: bool = False) -> tuple[str, float]:
        if not persons:
            return self.current_gesture, self.current_confidence

        best = max(persons, key=lambda p: p["score"])
        pid = best.get("track_id", 0)
        kpts = best["keypoints"]
        scores = best["joint_scores"]

        if pid not in self.history:
            self.history[pid] = deque(maxlen=self.window_size)

        core = [NOSE, LEFT_SHOULDER, RIGHT_SHOULDER]
        if any(scores[i] < JOINT_CONFIDENCE_THRESHOLD for i in core):
            return self.current_gesture, self.current_confidence

        frame_data = {
            "nose": kpts[NOSE].copy(),
            "left_shoulder": kpts[LEFT_SHOULDER].copy(),
            "right_shoulder": kpts[RIGHT_SHOULDER].copy(),
            "left_elbow": kpts[LEFT_ELBOW].copy() if scores[LEFT_ELBOW] > JOINT_CONFIDENCE_THRESHOLD else None,
            "right_elbow": kpts[RIGHT_ELBOW].copy() if scores[RIGHT_ELBOW] > JOINT_CONFIDENCE_THRESHOLD else None,
            "left_wrist": kpts[LEFT_WRIST].copy() if scores[LEFT_WRIST] > JOINT_CONFIDENCE_THRESHOLD else None,
            "right_wrist": kpts[RIGHT_WRIST].copy() if scores[RIGHT_WRIST] > JOINT_CONFIDENCE_THRESHOLD else None,
        }

        self.history[pid].append(frame_data)
        gesture, confidence = self._classify(pid, food_near_wrist)
        self.current_gesture = gesture
        self.current_confidence = confidence

        self._prune_stale(pid)
        return gesture, confidence

    def _classify(self, pid: int, drink_nearby: bool) -> tuple[str, float]:
        history = self.history[pid]
        if len(history) < 2:
            return "Resting", 0.5

        recent = list(history)
        curr = recent[-1]

        shoulder_width = np.linalg.norm(curr["left_shoulder"] - curr["right_shoulder"])
        head_width = max(shoulder_width * 0.5, 40.0)
        nose_threshold = head_width * WRIST_NOSE_RATIO
        shoulder_y = (curr["left_shoulder"][1] + curr["right_shoulder"][1]) / 2

        eating_signals = 0
        total_signals = 0

        # Signal 1: wrist near nose (either hand)
        wrist_near_face = False
        check_frames = recent[-min(5, len(recent)):]
        near_count = 0
        for frame in check_frames:
            for side in ("left_wrist", "right_wrist"):
                w = frame[side]
                if w is not None:
                    dist = np.linalg.norm(w - frame["nose"])
                    if dist < nose_threshold:
                        near_count += 1
                        break
        if near_count >= MIN_EATING_FRAMES:
            eating_signals += 2
            wrist_near_face = True
        total_signals += 2

        # Signal 2: bent elbow (either arm)
        elbow_bent = False
        for side_s, side_e, side_w in [
            ("left_shoulder", "left_elbow", "left_wrist"),
            ("right_shoulder", "right_elbow", "right_wrist"),
        ]:
            s, e, w = curr[side_s], curr[side_e], curr[side_w]
            if e is not None and w is not None:
                angle = _angle_at_joint(s, e, w)
                if angle < ELBOW_ANGLE_THRESHOLD:
                    eating_signals += 1
                    elbow_bent = True
                    break
        total_signals += 1

        # Signal 3: wrist above shoulder level (either hand is raised)
        wrist_raised = False
        for side in ("left_wrist", "right_wrist"):
            w = curr[side]
            if w is not None and w[1] < shoulder_y:
                wrist_raised = True
                eating_signals += 1
                break
        total_signals += 1

        confidence = eating_signals / total_signals if total_signals > 0 else 0.0

        if eating_signals >= 2:
            if drink_nearby and (wrist_near_face or wrist_raised):
                return "Drinking", min(1.0, confidence + 0.1)
            return "Eating", confidence

        if wrist_raised and elbow_bent and not wrist_near_face:
            return "Reaching", 0.6

        # Resting: both wrists below shoulders and still
        both_below = True
        for side in ("left_wrist", "right_wrist"):
            w = curr[side]
            if w is not None and w[1] < shoulder_y:
                both_below = False

        if both_below and len(recent) >= MIN_RESTING_FRAMES:
            still_count = 0
            for i in range(-min(MIN_RESTING_FRAMES, len(recent) - 1), 0):
                moved = False
                for side in ("left_wrist", "right_wrist"):
                    w_now = recent[i][side]
                    w_prev = recent[i - 1][side]
                    if w_now is not None and w_prev is not None:
                        if np.linalg.norm(w_now - w_prev) > 8.0:
                            moved = True
                if not moved:
                    still_count += 1
            if still_count >= MIN_RESTING_FRAMES - 3:
                return "Resting", 0.85

        return "Resting", 0.4

    def _prune_stale(self, active_pid: int) -> None:
        stale = [k for k in self.history if k != active_pid and len(self.history[k]) == 0]
        for k in stale:
            del self.history[k]
