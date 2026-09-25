from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

SYNTHETIC_MM_PER_PIXEL = 0.02


def _colour(rng: np.random.Generator, plastic: bool) -> tuple[int, int, int]:
    if plastic:
        options = [(215, 75, 40), (50, 70, 220), (45, 175, 45), (25, 210, 235), (50, 50, 50), (170, 170, 170)]
    else:
        options = [(45, 75, 100), (45, 85, 70), (55, 55, 65), (80, 100, 110)]
    return options[int(rng.integers(0, len(options)))]


def _polygon(rng: np.random.Generator, cx: int, cy: int, radius: int, vertices: int) -> np.ndarray:
    angles = np.sort(rng.uniform(0, np.pi * 2, vertices))
    radii = rng.uniform(radius * 0.45, radius, vertices)
    return np.array([[int(cx + np.cos(angle) * length), int(cy + np.sin(angle) * length)] for angle, length in zip(angles, radii)], dtype=np.int32)


def _fiber_points(rng: np.random.Generator, width: int, height: int) -> np.ndarray:
    margin = max(35, width // 7)
    cx, cy = int(rng.integers(margin, width - margin)), int(rng.integers(margin, height - margin))
    length = int(rng.integers(max(45, width // 25), max(80, width // 7)))
    angle = rng.uniform(0, np.pi * 2)
    normal = np.array([-np.sin(angle), np.cos(angle)])
    tangent = np.array([np.cos(angle), np.sin(angle)])
    points = []
    for t in np.linspace(-0.5, 0.5, 18):
        curve = np.sin((t + 0.5) * np.pi * rng.uniform(1.0, 1.6)) * rng.uniform(1, 4)
        point = np.array([cx, cy]) + tangent * t * length + normal * curve
        points.append(np.clip(point, [2, 2], [width - 3, height - 3]).astype(int))
    return np.asarray(points, dtype=np.int32)


def generate_image(params: dict[str, Any] | None = None) -> tuple[np.ndarray, list[dict[str, Any]]]:
    params = params or {}
    width = int(params.get("width", 1600))
    height = int(params.get("height", 1200))
    count = int(params.get("n_particles", 80))
    fibre_ratio = float(params.get("fibre_ratio", 0.35))
    noise = float(params.get("noise", 7))
    gradient = float(params.get("lighting_gradient", 0.12))
    rng = np.random.default_rng(params.get("seed"))
    yy, xx = np.mgrid[0:height, 0:width]
    radial = np.sqrt(((xx - width / 2) / width) ** 2 + ((yy - height / 2) / height) ** 2)
    base = 238 - radial * 255 * gradient + rng.normal(0, noise, (height, width))
    image = np.dstack([base, base, base]).clip(0, 255).astype(np.uint8)
    if params.get("circular_filter", True):
        cv2.circle(image, (width // 2, height // 2), int(min(width, height) * 0.48), (200, 200, 200), 2)
    labels: list[dict[str, Any]] = []
    for idx in range(1, count + 1):
        draw = float(rng.random())
        if draw < fibre_ratio:
            category, plastic = "fiber", True
        elif draw < fibre_ratio + 0.18:
            category, plastic = "pellet", True
        elif draw < fibre_ratio + 0.31:
            category, plastic = "film", True
        elif draw < fibre_ratio + 0.82:
            category, plastic = "fragment", True
        else:
            category, plastic = "non_plastic", False
        colour = _colour(rng, plastic)
        cx, cy = int(rng.integers(35, width - 35)), int(rng.integers(35, height - 35))
        if category == "fiber":
            points = _fiber_points(rng, width, height)
            thickness = int(rng.integers(3, 6))
            cv2.polylines(image, [points], False, colour, thickness, cv2.LINE_AA)
            x, y, w, h = cv2.boundingRect(points)
        elif category == "pellet":
            radius = int(rng.integers(7, 22))
            cv2.circle(image, (cx, cy), radius, colour, -1, cv2.LINE_AA)
            x, y, w, h = cx - radius, cy - radius, radius * 2, radius * 2
        elif category == "film":
            polygon = _polygon(rng, cx, cy, int(rng.integers(20, 55)), int(rng.integers(5, 10)))
            overlay = image.copy()
            cv2.fillPoly(overlay, [polygon], tuple(int((component + 170) / 2) for component in colour), cv2.LINE_AA)
            image = cv2.addWeighted(overlay, 0.7, image, 0.3, 0)
            x, y, w, h = cv2.boundingRect(polygon)
        else:
            radius = int(rng.integers(8, 30 if category == "fragment" else 22))
            polygon = _polygon(rng, cx, cy, radius, int(rng.integers(4, 9)))
            cv2.fillPoly(image, [polygon], colour, cv2.LINE_AA)
            x, y, w, h = cv2.boundingRect(polygon)
        labels.append({
            "id": idx, "shape_class": category, "label": "suspected_plastic" if plastic else "non_plastic",
            "bbox": {"x": int(x), "y": int(y), "w": int(w), "h": int(h)}, "mm_per_pixel": SYNTHETIC_MM_PER_PIXEL,
        })
    return image, labels


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a synthetic filter image for MicroPlast Screen.")
    parser.add_argument("--output", type=Path, default=Path("data/raw/synthetic.png"))
    parser.add_argument("--particles", type=int, default=80)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()
    image, labels = generate_image({"n_particles": args.particles, "seed": args.seed})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(args.output), image)
    labels_path = args.output.with_suffix(".json")
    labels_path.write_text(json.dumps({"mm_per_pixel": SYNTHETIC_MM_PER_PIXEL, "particles": labels}, indent=2), encoding="utf-8")
    print(f"Saved {args.output} and {labels_path} with {len(labels)} labelled particles")


if __name__ == "__main__":
    main()
