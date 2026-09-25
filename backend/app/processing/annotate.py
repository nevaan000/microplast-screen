from __future__ import annotations

from typing import Any

import cv2
import numpy as np

COLOURS = {
    "fiber": (249, 137, 45),
    "fragment": (63, 142, 252),
    "film": (198, 92, 235),
    "pellet": (66, 190, 122),
    "non_plastic": (135, 145, 158),
}


def annotate(image: np.ndarray, particles: list[dict[str, Any]]) -> np.ndarray:
    result = image.copy()
    scale = max(0.45, min(image.shape[:2]) / 1500)
    for particle in particles:
        x, y, w, h = (int(particle[key]) for key in ("bbox_x", "bbox_y", "bbox_w", "bbox_h"))
        colour = COLOURS.get(particle["shape_class"], COLOURS["non_plastic"])
        cv2.rectangle(result, (x, y), (x + w, y + h), colour, max(1, round(2 * scale)))
        label = f"{particle['idx']} {particle['shape_class']}"
        baseline_y = max(14, y - 4)
        cv2.putText(result, label, (x, baseline_y), cv2.FONT_HERSHEY_SIMPLEX, 0.38 * scale, colour, max(1, round(scale)), cv2.LINE_AA)
    legend_y = 22
    for category, colour in COLOURS.items():
        cv2.rectangle(result, (12, legend_y - 10), (23, legend_y + 1), colour, -1)
        cv2.putText(result, category.replace("_", " "), (28, legend_y), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (25, 35, 46), 1, cv2.LINE_AA)
        legend_y += 18
    return result
