from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass
class BoundingBox:
    """Single bounding box in absolute pixel coordinates."""

    class_name: str = ""
    xmin: float = 0.0
    ymin: float = 0.0
    xmax: float = 0.0
    ymax: float = 0.0
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    @property
    def width(self) -> float:
        return self.xmax - self.xmin

    @property
    def height(self) -> float:
        return self.ymax - self.ymin

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "class_name": self.class_name,
            "xmin": self.xmin,
            "ymin": self.ymin,
            "xmax": self.xmax,
            "ymax": self.ymax,
        }

    @classmethod
    def from_dict(cls, d: dict) -> BoundingBox:
        return cls(
            id=d.get("id", uuid.uuid4().hex[:8]),
            class_name=d.get("class_name", ""),
            xmin=float(d.get("xmin", 0)),
            ymin=float(d.get("ymin", 0)),
            xmax=float(d.get("xmax", 0)),
            ymax=float(d.get("ymax", 0)),
        )


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
