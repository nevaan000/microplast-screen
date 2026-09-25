from __future__ import annotations

from typing import Any

import cv2
import numpy as np

from .calibration import physical_measurements


def dominant_colour_name(mean_b: float, mean_g: float, mean_r: float, mean_h: float, mean_s: float, mean_v: float) -> str:
    if mean_v < 55:
        return "black"
    if mean_s < 24:
        if mean_v > 205:
            return "white"
        if mean_v > 145:
            return "transparent-ish"
        return "gray"
    hue = mean_h * 2
    if hue < 15 or hue >= 345:
        return "red"
    if hue < 35:
        return "orange"
    if hue < 65:
        return "yellow"
    if hue < 165:
        return "green"
    if hue < 255:
        return "blue"
    if hue < 345:
        return "brown" if mean_v < 150 else "red"
    return "brown"


def extract_particles(
    mask: np.ndarray,
    image: np.ndarray,
    gray: np.ndarray,
    settings: dict[str, Any],
    mm_per_pixel: float | None,
) -> list[dict[str, Any]]:
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    max_area = mask.shape[0] * mask.shape[1] * float(settings.get("max_area_percent", 25)) / 100
    min_area = float(settings.get("min_area_px", 12))
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    particles: list[dict[str, Any]] = []
    for contour in contours:
        area = float(cv2.contourArea(contour))
        if area < min_area or area > max_area:
            continue
        perimeter = float(cv2.arcLength(contour, True))
        if perimeter <= 0:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        (_, _), (side_a, side_b), _ = cv2.minAreaRect(contour)
        length_px, width_px = sorted((float(side_a), float(side_b)), reverse=True)
        if width_px <= 0:
            continue
        moments = cv2.moments(contour)
        if moments["m00"]:
            centroid_x = moments["m10"] / moments["m00"]
            centroid_y = moments["m01"] / moments["m00"]
        else:
            centroid_x, centroid_y = x + w / 2, y + h / 2
        hull = cv2.convexHull(contour)
        hull_area = float(cv2.contourArea(hull))
        contour_mask = np.zeros(mask.shape, dtype=np.uint8)
        cv2.drawContours(contour_mask, [contour], -1, 255, -1)
        mean_b, mean_g, mean_r, _ = cv2.mean(image, mask=contour_mask)
        mean_h, mean_s, mean_v, _ = cv2.mean(hsv, mask=contour_mask)
        texture_values = gray[contour_mask > 0]
        measurements = physical_measurements(length_px, width_px, area, mm_per_pixel)
        particles.append({
            "idx": 0,
            "centroid_x": round(float(centroid_x), 3),
            "centroid_y": round(float(centroid_y), 3),
            "bbox_x": int(x), "bbox_y": int(y), "bbox_w": int(w), "bbox_h": int(h),
            "area_px": round(area, 3), "perimeter_px": round(perimeter, 3),
            "length_px": round(length_px, 3), "width_px": round(width_px, 3),
            "aspect_ratio": round(length_px / width_px, 4),
            "circularity": round(float(4 * np.pi * area / (perimeter * perimeter)), 4),
            "solidity": round(area / hull_area, 4) if hull_area else 0.0,
            "extent": round(area / (w * h), 4) if w and h else 0.0,
            "mean_b": round(mean_b, 3), "mean_g": round(mean_g, 3), "mean_r": round(mean_r, 3),
            "mean_h": round(mean_h, 3), "mean_s": round(mean_s, 3), "mean_v": round(mean_v, 3),
            "color_name": dominant_colour_name(mean_b, mean_g, mean_r, mean_h, mean_s, mean_v),
            "texture_std": round(float(np.std(texture_values)), 3),
            **measurements,
        })
    particles.sort(key=lambda item: (item["centroid_y"], item["centroid_x"]))
    for index, particle in enumerate(particles, start=1):
        particle["idx"] = index
    return particles
