from __future__ import annotations

from typing import Any

import cv2
import numpy as np


def _odd(value: int) -> int:
    return max(3, value | 1)


def _intensity_mask(gray: np.ndarray, settings: dict[str, Any]) -> np.ndarray:
    method = settings.get("threshold_method", "otsu")
    light_filter = settings.get("background_mode", "light_filter") == "light_filter"
    threshold_type = cv2.THRESH_BINARY_INV if light_filter else cv2.THRESH_BINARY
    if method == "adaptive":
        return cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            threshold_type,
            _odd(int(settings.get("adaptive_block_size", 31))),
            int(settings.get("adaptive_c", 4)),
        )
    if method == "fixed":
        _, mask = cv2.threshold(gray, int(settings.get("fixed_threshold", 125)), 255, threshold_type)
        return mask
    _, mask = cv2.threshold(gray, 0, 255, threshold_type | cv2.THRESH_OTSU)
    return mask


def _apply_roi(mask: np.ndarray, gray: np.ndarray, settings: dict[str, Any]) -> np.ndarray:
    h, w = mask.shape
    margin = int(min(h, w) * float(settings.get("border_margin_percent", 3)) / 100)
    if margin:
        mask[:margin, :] = 0
        mask[-margin:, :] = 0
        mask[:, :margin] = 0
        mask[:, -margin:] = 0
    mode = settings.get("roi_mode", "none")
    if mode not in {"circle", "manual", "auto"}:
        return mask
    if mode in {"circle", "manual"}:
        cx = int(w * float(settings.get("roi_center_x", 0.5)))
        cy = int(h * float(settings.get("roi_center_y", 0.5)))
        radius = int(min(h, w) * float(settings.get("roi_radius_percent", 48)) / 100)
    else:
        blurred = cv2.medianBlur(gray, 7)
        circles = cv2.HoughCircles(
            blurred, cv2.HOUGH_GRADIENT, dp=1.2, minDist=min(h, w) // 2,
            param1=100, param2=35, minRadius=int(min(h, w) * 0.3), maxRadius=int(min(h, w) * 0.53),
        )
        if circles is None:
            return mask
        cx, cy, radius = max(np.round(circles[0]).astype(int), key=lambda circle: circle[2])
    roi = np.zeros_like(mask)
    cv2.circle(roi, (cx, cy), radius, 255, -1)
    return cv2.bitwise_and(mask, roi)


def segment(preprocessed: dict[str, np.ndarray], settings: dict[str, Any]) -> np.ndarray:
    intensity = _intensity_mask(preprocessed["enhanced"], settings)
    saturation = preprocessed["hsv"][:, :, 1]
    colour = cv2.threshold(saturation, int(settings.get("sat_threshold", 60)), 255, cv2.THRESH_BINARY)[1]
    mask = cv2.bitwise_or(intensity, colour)
    open_size = max(1, int(settings.get("opening_kernel", 3)))
    close_size = max(1, int(settings.get("closing_kernel", 3)))
    opening = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (open_size, open_size))
    closing = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (close_size, close_size))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, opening, iterations=int(settings.get("opening_iterations", 1)))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, closing, iterations=int(settings.get("closing_iterations", 2)))
    return _apply_roi(mask, preprocessed["gray"], settings)
