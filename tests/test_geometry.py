from alchemyannotate.utils.geometry import (
    polygon_bounding_rect,
    normalize_points,
    denormalize_points,
    clamp_points_to_image,
)


def test_polygon_bounding_rect():
    points = [[10, 20], [50, 10], [90, 60], [30, 80]]
    xmin, ymin, xmax, ymax = polygon_bounding_rect(points)
    assert xmin == 10
    assert ymin == 10
    assert xmax == 90
    assert ymax == 80


def test_polygon_bounding_rect_triangle():
    points = [[100, 100], [200, 50], [150, 200]]
    xmin, ymin, xmax, ymax = polygon_bounding_rect(points)
    assert xmin == 100
    assert ymin == 50
    assert xmax == 200
    assert ymax == 200


def test_normalize_denormalize_roundtrip():
    points = [[100, 200], [300, 400], [500, 100]]
    img_w, img_h = 640, 480
    norm = normalize_points(points, img_w, img_h)
    restored = denormalize_points(norm, img_w, img_h)
    for orig, rest in zip(points, restored):
        assert abs(orig[0] - rest[0]) < 1e-9
        assert abs(orig[1] - rest[1]) < 1e-9


def test_normalize_points_values():
    points = [[320, 240]]
    norm = normalize_points(points, 640, 480)
    assert abs(norm[0][0] - 0.5) < 1e-9
    assert abs(norm[0][1] - 0.5) < 1e-9


def test_clamp_points_to_image():
    points = [[-10, -20], [700, 500], [320, 240]]
    clamped = clamp_points_to_image(points, 640, 480)
    assert clamped[0] == [0.0, 0.0]
    assert clamped[1] == [640.0, 480.0]
    assert clamped[2] == [320, 240]
