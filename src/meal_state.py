import threading
import time
from collections import deque
from dataclasses import dataclass, field


@dataclass
class MealEvent:
    timestamp: float
    label: str
    track_id: int
    category: str  # "food" or "utensil"


class MealState:
    def __init__(self, stale_timeout: float = 3.0, max_events: int = 50):
        self._lock = threading.Lock()
        self.stale_timeout = stale_timeout
        self.meal_start_time: float | None = None
        self.current_food_items: dict[int, dict] = {}
        self.current_utensils: dict[int, dict] = {}
        self.seen_track_ids: set[int] = set()
        self.event_log: deque[MealEvent] = deque(maxlen=max_events)
        self.gesture: str = "Resting"
        self.gesture_confidence: float = 0.0
        self.gesture_source: str = "not connected"

    def update(self, food_detections: list[dict], utensil_detections: list[dict]) -> None:
        now = time.time()
        with self._lock:
            if self.meal_start_time is None and (food_detections or utensil_detections):
                self.meal_start_time = now

            for det in food_detections:
                tid = det["track_id"]
                self.current_food_items[tid] = {
                    "label": det["label"],
                    "score": det["score"],
                    "last_seen": now,
                }
                if tid not in self.seen_track_ids:
                    self.seen_track_ids.add(tid)
                    self.event_log.appendleft(
                        MealEvent(now, det["label"], tid, "food")
                    )

            for det in utensil_detections:
                tid = det["track_id"]
                self.current_utensils[tid] = {
                    "label": det["label"],
                    "score": det["score"],
                    "last_seen": now,
                }
                if tid not in self.seen_track_ids:
                    self.seen_track_ids.add(tid)
                    self.event_log.appendleft(
                        MealEvent(now, det["label"], tid, "utensil")
                    )

            self._prune_stale(now)

    def _prune_stale(self, now: float) -> None:
        for store in (self.current_food_items, self.current_utensils):
            stale = [k for k, v in store.items() if now - v["last_seen"] > self.stale_timeout]
            for k in stale:
                del store[k]

    def update_gesture(self, gesture: str, confidence: float, source: str = "camera") -> None:
        with self._lock:
            self.gesture = gesture
            self.gesture_confidence = confidence
            self.gesture_source = source

    def get_snapshot(self) -> dict:
        with self._lock:
            now = time.time()
            duration = now - self.meal_start_time if self.meal_start_time else 0.0
            return {
                "duration": duration,
                "food_items": dict(self.current_food_items),
                "utensils": dict(self.current_utensils),
                "gesture": self.gesture,
                "gesture_confidence": self.gesture_confidence,
                "gesture_source": self.gesture_source,
                "events": list(self.event_log),
            }
