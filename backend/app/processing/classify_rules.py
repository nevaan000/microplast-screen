from __future__ import annotations

from typing import Any

VIVID_COLOURS = {"blue", "red", "green", "yellow", "orange", "black", "white"}


def classify_particle(feature: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    aspect_ratio = feature["aspect_ratio"]
    width_px = feature["width_px"]
    width_mm = feature.get("width_mm")
    is_narrow = width_px <= float(settings.get("fiber_width_px", 12))
    if width_mm is not None:
        is_narrow = is_narrow or width_mm <= float(settings.get("fiber_width_mm", 0.3))
    if aspect_ratio >= float(settings.get("fiber_aspect_ratio", 3.0)) and is_narrow:
        shape = "fiber"
    elif feature["circularity"] >= 0.80 and aspect_ratio <= 1.5:
        shape = "pellet"
    elif (feature["area_px"] >= max(350, float(settings.get("min_area_px", 12)) * 20) and feature["solidity"] <= 0.75 and feature["texture_std"] < 38) or (
        feature["area_px"] >= 800 and feature["mean_s"] < 40 and feature["texture_std"] < 22
    ):
        shape = "film"
    else:
        shape = "fragment"

    score = {"fiber": 0.66, "pellet": 0.64, "film": 0.57, "fragment": 0.55}[shape]
    if feature["color_name"] in VIVID_COLOURS:
        score += 0.10
    if feature["color_name"] in {"brown", "transparent-ish"}:
        score -= 0.18
    if feature["solidity"] >= 0.85:
        score += 0.07
    if feature["texture_std"] < 20:
        score += 0.08
    elif feature["texture_std"] > 45:
        score -= 0.18
    if feature["color_name"] == "brown" and feature["mean_s"] < 90:
        score -= 0.12
    score = round(max(0.01, min(0.99, score)), 4)
    label = "suspected_plastic" if score >= float(settings.get("plastic_threshold", 0.55)) else "non_plastic"
    confidence = score if label == "suspected_plastic" else 1 - score
    return {"shape_class": shape if label == "suspected_plastic" else "non_plastic", "label": label, "confidence": confidence, "plastic_score": score}
