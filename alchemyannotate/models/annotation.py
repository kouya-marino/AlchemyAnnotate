from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass
class BoundingBox:
    """Single annotation in absolute pixel coordinates. Supports bbox and polygon types."""

    class_name: str = ""
    xmin: float = 0.0
    ymin: float = 0.0
    xmax: float = 0.0
    ymax: float = 0.0
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    annotation_type: str = "bbox"
    points: list[list[float]] = field(default_factory=list)

    @property
    def width(self) -> float:
        return self.xmax - self.xmin

    @property
    def height(self) -> float:
        return self.ymax - self.ymin

    def compute_bbox_from_points(self) -> None:
        """Set xmin/ymin/xmax/ymax from polygon points."""
        if not self.points:
            return
        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        self.xmin = min(xs)
        self.ymin = min(ys)
        self.xmax = max(xs)
        self.ymax = max(ys)

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "class_name": self.class_name,
            "annotation_type": self.annotation_type,
            "xmin": self.xmin,
            "ymin": self.ymin,
            "xmax": self.xmax,
            "ymax": self.ymax,
        }
        if self.points:
            d["points"] = self.points
        return d

    @classmethod
    def from_dict(cls, d: dict) -> BoundingBox:
        box = cls(
            id=d.get("id", uuid.uuid4().hex[:8]),
            class_name=d.get("class_name", ""),
            annotation_type=d.get("annotation_type", "bbox"),
            xmin=float(d.get("xmin", 0)),
            ymin=float(d.get("ymin", 0)),
            xmax=float(d.get("xmax", 0)),
            ymax=float(d.get("ymax", 0)),
            points=d.get("points", []),
        )
        return box


@dataclass
class ImageAnnotation:
    """All annotations for a single image."""

    image_filename: str
    image_width: int = 0
    image_height: int = 0
    boxes: list[BoundingBox] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "image_filename": self.image_filename,
            "image_width": self.image_width,
            "image_height": self.image_height,
            "boxes": [b.to_dict() for b in self.boxes],
        }

    @classmethod
    def from_dict(cls, d: dict) -> ImageAnnotation:
        return cls(
            image_filename=d["image_filename"],
            image_width=int(d.get("image_width", 0)),
            image_height=int(d.get("image_height", 0)),
            boxes=[BoundingBox.from_dict(b) for b in d.get("boxes", [])],
        )
