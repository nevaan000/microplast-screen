from __future__ import annotations

from typing import Any

import cv2
import numpy as np


def preprocess_image(image: np.ndarray, settings: dict[str, Any]) -> dict[str, np.ndarray]:
    """Prepare grayscale and HSV representations while preserving the source image."""
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("Expected a BGR colour image")
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    corrected = gray
    if settings.get("illumination_correction", True):
        kernel = max(3, (image.shape[1] // 8) | 1)
        background = cv2.GaussianBlur(gray, (kernel, kernel), 0)
        corrected = cv2.divide(gray, background, scale=200)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(corrected)
    denoised = cv2.medianBlur(enhanced, 3)
    denoised = cv2.GaussianBlur(denoised, (5, 5), 0)
    return {"original": image, "gray": gray, "hsv": hsv, "enhanced": denoised}
