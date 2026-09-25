import numpy as np

from backend.app.processing.pipeline import analyze_frames
from backend.app.processing.segmentation import _apply_roi
from scripts.generate_synthetic import generate_image


def test_clean_synthetic_particle_count_and_shape_recall():
    image, truth = generate_image({"width": 800, "height": 600, "n_particles": 30, "noise": 0, "seed": 1})
    result = analyze_frames([image], mm_per_pixel=0.02)
    detected = result["summary"]["total_particles"]
    assert abs(detected - len(truth)) / len(truth) <= 0.15
    for class_name, summary_key in (("fiber", "fibers"), ("pellet", "pellets")):
        expected = sum(item["shape_class"] == class_name for item in truth)
        if expected:
            assert result["summary"][summary_key] / expected >= 0.5


def test_blank_filter_has_at_most_two_particles():
    image = np.full((600, 800, 3), 238, dtype=np.uint8)
    result = analyze_frames([image])
    assert result["summary"]["total_particles"] <= 2


def test_circle_roi_excludes_pixels_outside_configured_circle():
    mask = np.full((100, 100), 255, dtype=np.uint8)
    result = _apply_roi(mask, np.zeros_like(mask), {
        "roi_mode": "circle",
        "border_margin_percent": 0,
        "roi_center_x": 0.5,
        "roi_center_y": 0.5,
        "roi_radius_percent": 25,
    })
    assert result[50, 50] == 255
    assert result[0, 0] == 0
