"""Patch hailo-apps BYTETracker to use NumPy IoU fallback instead of cython_bbox.

cython_bbox requires a C++ compiler to build from source. This patch adds a
pure NumPy fallback so the tracker works without it.
"""
import os

MATCHING_PY = os.path.join(
    "deps", "hailo-apps", "hailo_apps", "python", "core", "tracker", "matching.py"
)

OLD = "from cython_bbox import bbox_overlaps as bbox_ious"

NEW = """try:
    from cython_bbox import bbox_overlaps as bbox_ious
except ImportError:
    def bbox_ious(atlbrs, btlbrs):
        import numpy as np
        x11, y11, x12, y12 = atlbrs[:, 0], atlbrs[:, 1], atlbrs[:, 2], atlbrs[:, 3]
        x21, y21, x22, y22 = btlbrs[:, 0], btlbrs[:, 1], btlbrs[:, 2], btlbrs[:, 3]
        xi1 = np.maximum(x11[:, None], x21[None, :])
        yi1 = np.maximum(y11[:, None], y21[None, :])
        xi2 = np.minimum(x12[:, None], x22[None, :])
        yi2 = np.minimum(y12[:, None], y22[None, :])
        inter = np.maximum(xi2 - xi1, 0) * np.maximum(yi2 - yi1, 0)
        area1 = (x12 - x11) * (y12 - y11)
        area2 = (x22 - x21) * (y22 - y21)
        union = area1[:, None] + area2[None, :] - inter
        return inter / np.maximum(union, 1e-6)"""

if not os.path.exists(MATCHING_PY):
    print(f"  Skipping patch — {MATCHING_PY} not found")
else:
    with open(MATCHING_PY, "r") as f:
        content = f.read()
    if OLD in content:
        content = content.replace(OLD, NEW)
        with open(MATCHING_PY, "w") as f:
            f.write(content)
        print("  Patched matching.py — cython_bbox fallback added")
    else:
        print("  matching.py already patched, skipping")
