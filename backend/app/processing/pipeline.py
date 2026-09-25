from __future__ import annotations

import time
from statistics import median
from typing import Any

import cv2
import numpy as np

from ..db import get_settings
from .annotate import annotate
from .classify_rules import classify_particle
from .features import extract_particles
from .preprocess import preprocess_image
from .segmentation import segment


def median_stack(frames: list[np.ndarray]) -> np.ndarray:
    if not frames:
        raise ValueError("At least one image frame is required")
    first_shape = frames[0].shape
    if any(frame.shape != first_shape for frame in frames):
        raise ValueError("All frames must have the same dimensions")
    if len(frames) == 1:
        return frames[0].copy()
    return np.median(np.stack(frames, axis=0), axis=0).astype(np.uint8)


def _histogram(particles: list[dict[str, Any]], settings: dict[str, Any], calibrated: bool) -> dict[str, Any]:
    if calibrated:
        values = [particle["length_mm"] for particle in particles if particle["length_mm"] is not None]
        bins = [float(value) for value in settings.get("size_bins_mm", [0.2, 0.5, 1.0, 2.0, 5.0])]
        labels = [f"<{bins[0]:g}"] + [f"{bins[i - 1]:g}–{bins[i]:g}" for i in range(1, len(bins))] + [f">{bins[-1]:g}"]
        unit = "mm"
    else:
        values = [particle["length_px"] for particle in particles]
        bins = [50, 100, 250, 500, 1000]
        labels = [f"<{bins[0]}"] + [f"{bins[i - 1]}–{bins[i]}" for i in range(1, len(bins))] + [f">{bins[-1]}"]
        unit = "px"
    counts = [0] * (len(bins) + 1)
    for value in values:
        bucket = next((index for index, threshold in enumerate(bins) if value < threshold), len(bins))
        counts[bucket] += 1
    return {"labels": labels, "counts": counts, "unit": unit, "larger_than_microplastic": counts[-1] if calibrated else 0}


def analyze_frames(
    frames: list[np.ndarray],
    settings: dict[str, Any] | None = None,
    mm_per_pixel: float | None = None,
    volume_ml: float | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    settings = settings or get_settings()
    source = median_stack(frames)
    prepared = preprocess_image(source, settings)
    mask = segment(prepared, settings)
    particles = extract_particles(mask, source, prepared["gray"], settings, mm_per_pixel)
    for particle in particles:
        rules = classify_particle(particle, settings)
        particle.update(rules)
    mode = settings.get("classifier_mode", "hybrid")
    if mode in {"ml", "hybrid"}:
        try:
            from ..ml.model import predict_particle
            for particle in particles:
                prediction = predict_particle(particle)
                if prediction:
                    if mode == "ml":
                        particle.update(prediction)
                    else:
                        rule_score = particle["plastic_score"]
                        score = round((rule_score + prediction["plastic_score"]) / 2, 4)
                        shape = prediction["shape_class"] if prediction["confidence"] > 0.6 else particle["shape_class"]
                        label = "suspected_plastic" if score >= float(settings.get("plastic_threshold", 0.55)) else "non_plastic"
                        confidence = score if label == "suspected_plastic" else round(1 - score, 4)
                        particle.update({"shape_class": shape if label == "suspected_plastic" else "non_plastic", "label": label, "confidence": confidence, "plastic_score": score})
        except (ImportError, FileNotFoundError, ValueError):
            pass
    annotated = annotate(source, particles)
    shape_counts = {name: sum(particle["shape_class"] == name for particle in particles) for name in ("fiber", "fragment", "film", "pellet", "non_plastic")}
    suspected = sum(particle["label"] == "suspected_plastic" for particle in particles)
    lengths_mm = [particle["length_mm"] for particle in particles if particle["length_mm"] is not None]
    suspected_confidences = [particle["confidence"] for particle in particles if particle["label"] == "suspected_plastic"]
    total = len(particles)
    concentration = suspected / (volume_ml / 1000) if volume_ml else None
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    summary = {
        "total_particles": total,
        "suspected_plastic": suspected,
        "non_plastic": total - suspected,
        "fibers": shape_counts["fiber"],
        "fragments": shape_counts["fragment"],
        "films": shape_counts["film"],
        "pellets": shape_counts["pellet"],
        "mean_length_mm": round(float(np.mean(lengths_mm)), 4) if lengths_mm else None,
        "median_length_mm": round(float(median(lengths_mm)), 4) if lengths_mm else None,
        "min_length_mm": round(min(lengths_mm), 4) if lengths_mm else None,
        "max_length_mm": round(max(lengths_mm), 4) if lengths_mm else None,
        "concentration_per_l": round(concentration, 3) if concentration is not None else None,
        "sample_confidence": round(float(np.mean(suspected_confidences)) * 100, 2) if suspected_confidences else 0.0,
        "min_reliable_size_mm": round(float(settings.get("min_reliable_px", 5)) * mm_per_pixel, 4) if mm_per_pixel else None,
        "processing_ms": elapsed_ms,
        "size_histogram": _histogram(particles, settings, mm_per_pixel is not None),
    }
    return {"source": source, "annotated": annotated, "mask": mask, "particles": particles, "summary": summary, "n_frames": len(frames)}
