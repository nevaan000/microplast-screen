from backend.app.processing.calibration import calculate_mm_per_pixel, physical_measurements


def test_pixel_to_mm_conversion():
    mm_per_pixel = calculate_mm_per_pixel(500, 10)
    assert mm_per_pixel == 0.02
    values = physical_measurements(100, 25, 2500, mm_per_pixel)
    assert values["length_mm"] == 2
    assert values["width_mm"] == 0.5
    assert values["area_mm2"] == 1
