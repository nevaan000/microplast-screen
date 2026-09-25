from __future__ import annotations


def calculate_mm_per_pixel(pixel_distance: float, real_mm: float) -> float:
    if pixel_distance <= 0 or real_mm <= 0:
        raise ValueError("Calibration distances must be positive")
    return real_mm / pixel_distance


def physical_measurements(length_px: float, width_px: float, area_px: float, mm_per_pixel: float | None) -> dict[str, float | None]:
    if mm_per_pixel is None:
        return {"length_mm": None, "width_mm": None, "area_mm2": None, "equivalent_diameter_mm": None}
    area_mm2 = area_px * mm_per_pixel * mm_per_pixel
    from math import pi, sqrt
    return {
        "length_mm": length_px * mm_per_pixel,
        "width_mm": width_px * mm_per_pixel,
        "area_mm2": area_mm2,
        "equivalent_diameter_mm": sqrt(4 * area_mm2 / pi),
    }
