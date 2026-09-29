import time
import cv2
import numpy as np


class DashboardRenderer:
    def __init__(self, width: int = 400, frame_height: int = 480):
        self.width = width
        self.height = frame_height
        self.bg_color = (30, 30, 30)
        self.text_color = (255, 255, 255)
        self.accent_color = (0, 200, 120)
        self.dim_color = (140, 140, 140)
        self.separator_color = (80, 80, 80)
        self.font = cv2.FONT_HERSHEY_SIMPLEX

    def render(self, snapshot: dict) -> np.ndarray:
        panel = np.full((self.height, self.width, 3), self.bg_color, dtype=np.uint8)
        y = 10

        y = self._draw_header(panel, y, snapshot["duration"])
        y = self._draw_separator(panel, y)
        y = self._draw_section(panel, y, "Food Items", snapshot["food_items"], self.accent_color)
        y = self._draw_separator(panel, y)
        y = self._draw_section(panel, y, "Utensils", snapshot["utensils"], (100, 180, 255))
        y = self._draw_separator(panel, y)
        y = self._draw_gesture(panel, y, snapshot["gesture"], snapshot["gesture_confidence"], snapshot["gesture_source"])
        y = self._draw_separator(panel, y)
        self._draw_event_log(panel, y, snapshot["events"])

        return panel

    def _put_text(self, img, text, pos, scale, color, thickness=1):
        bx, by = pos
        cv2.putText(img, text, (bx, by), self.font, scale, (0, 0, 0), thickness + 1, cv2.LINE_AA)
        cv2.putText(img, text, (bx, by), self.font, scale, color, thickness, cv2.LINE_AA)

    def _draw_header(self, panel, y, duration):
        y += 30
        self._put_text(panel, "MEAL MONITOR", (15, y), 0.8, self.text_color, 2)
        y += 30
        mins, secs = divmod(int(duration), 60)
        hrs, mins = divmod(mins, 60)
        time_str = f"Duration: {hrs:02d}:{mins:02d}:{secs:02d}"
        self._put_text(panel, time_str, (15, y), 0.55, self.accent_color)
        y += 10
        return y

    def _draw_separator(self, panel, y):
        y += 8
        cv2.line(panel, (15, y), (self.width - 15, y), self.separator_color, 1)
        y += 8
        return y

    def _draw_section(self, panel, y, title, items, color):
        y += 20
        self._put_text(panel, title, (15, y), 0.55, self.text_color)
        y += 5
        if not items:
            y += 18
            self._put_text(panel, "  --", (15, y), 0.45, self.dim_color)
            y += 5
            return y

        seen_labels = {}
        for tid, info in items.items():
            label = info["label"]
            if label not in seen_labels or info["score"] > seen_labels[label]:
                seen_labels[label] = info["score"]

        for label, score in sorted(seen_labels.items(), key=lambda x: -x[1]):
            y += 20
            if y > self.height - 20:
                break
            text = f"  * {label} ({score * 100:.0f}%)"
            self._put_text(panel, text, (15, y), 0.45, color)

        y += 5
        return y

    def _draw_gesture(self, panel, y, gesture, confidence, source):
        y += 20
        self._put_text(panel, "Gesture", (15, y), 0.55, self.text_color)
        y += 22
        if source == "not connected":
            self._put_text(panel, "  [no pose model]", (15, y), 0.45, self.dim_color)
        else:
            gesture_color = {
                "Eating": (0, 220, 100),
                "Drinking": (255, 180, 0),
                "Reaching": (100, 180, 255),
                "Resting": (140, 140, 140),
            }.get(gesture, (180, 130, 255))
            text = f"  {gesture} ({confidence * 100:.0f}%)"
            self._put_text(panel, text, (15, y), 0.5, gesture_color)
            y += 20
            self._put_text(panel, f"  [{source}]", (15, y), 0.35, self.dim_color)
        y += 5
        return y

    def _draw_event_log(self, panel, y, events):
        y += 20
        self._put_text(panel, "Event Log", (15, y), 0.55, self.text_color)
        y += 5

        max_events = min(len(events), (self.height - y - 10) // 18)
        for i in range(max_events):
            y += 18
            if y > self.height - 10:
                break
            ev = events[i]
            ts = time.strftime("%H:%M:%S", time.localtime(ev.timestamp))
            text = f"  {ts} {ev.label}"
            self._put_text(panel, text, (15, y), 0.4, self.dim_color)
