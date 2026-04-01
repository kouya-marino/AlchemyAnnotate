from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtCore import QRectF

    from alchemyannotate.models.annotation import BoundingBox


def clamp_box_to_image(box: BoundingBox, img_w: int, img_h: int) -> None:
    """Clamp box coordinates to image bounds (mutates in place)."""
    box.xmin = max(0.0, min(box.xmin, float(img_w)))
    box.ymin = max(0.0, min(box.ymin, float(img_h)))
    box.xmax = max(0.0, min(box.xmax, float(img_w)))
    box.ymax = max(0.0, min(box.ymax, float(img_h)))


def normalize_coords(
    xmin: float, ymin: float, xmax: float, ymax: float, img_w: int, img_h: int
) -> tuple[float, float, float, float]:
    """Convert absolute coords to YOLO normalized (cx, cy, w, h)."""
    cx = ((xmin + xmax) / 2.0) / img_w
    cy = ((ymin + ymax) / 2.0) / img_h
    w = (xmax - xmin) / img_w
    h = (ymax - ymin) / img_h
    return cx, cy, w, h


def denormalize_coords(
    cx: float, cy: float, w: float, h: float, img_w: int, img_h: int
) -> tuple[float, float, float, float]:
    """Convert YOLO normalized (cx, cy, w, h) to absolute (xmin, ymin, xmax, ymax)."""
    abs_w = w * img_w
    abs_h = h * img_h
    xmin = cx * img_w - abs_w / 2.0
    ymin = cy * img_h - abs_h / 2.0
    xmax = xmin + abs_w
    ymax = ymin + abs_h
    return xmin, ymin, xmax, ymax


def qrectf_to_coords(rect: QRectF) -> tuple[float, float, float, float]:
    """Convert QRectF to (xmin, ymin, xmax, ymax), normalizing flipped rects."""
    x1, y1 = rect.left(), rect.top()
    x2, y2 = rect.right(), rect.bottom()
    return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)


# -- Polygon helpers --


def polygon_bounding_rect(
    points: list[list[float]],
) -> tuple[float, float, float, float]:
    """Compute (xmin, ymin, xmax, ymax) bounding rect from polygon points."""
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def normalize_points(
    points: list[list[float]], img_w: int, img_h: int
) -> list[list[float]]:
    """Normalize polygon points to 0-1 range for YOLO-seg export."""
    return [[p[0] / img_w, p[1] / img_h] for p in points]


def denormalize_points(
    points: list[list[float]], img_w: int, img_h: int
) -> list[list[float]]:
    """Denormalize polygon points from 0-1 range to absolute pixels."""
    return [[p[0] * img_w, p[1] * img_h] for p in points]


def clamp_points_to_image(
    points: list[list[float]], img_w: int, img_h: int
) -> list[list[float]]:
    """Clamp polygon points to image bounds."""
    return [
        [max(0.0, min(p[0], float(img_w))), max(0.0, min(p[1], float(img_h)))]
        for p in points
    ]
