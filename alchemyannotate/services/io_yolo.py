from __future__ import annotations

from pathlib import Path

from alchemyannotate.models.annotation import BoundingBox, ImageAnnotation
from alchemyannotate.utils.geometry import (
    normalize_coords, denormalize_coords,
    normalize_points, denormalize_points, polygon_bounding_rect,
)


class YoloIO:
    """Read/write YOLO format annotation files (detection + segmentation)."""

    @staticmethod
    def read(txt_path: Path, img_w: int, img_h: int, class_list: list[str]) -> ImageAnnotation:
        filename = txt_path.stem
        annotation = ImageAnnotation(
            image_filename=filename,
            image_width=img_w,
            image_height=img_h,
        )
        if not txt_path.exists():
            return annotation

        text = txt_path.read_text(encoding="utf-8").strip()
        if not text:
            return annotation

        for line in text.splitlines():
            parts = line.strip().split()
            if len(parts) < 5:
                continue
            class_idx = int(parts[0])
            class_name = class_list[class_idx] if class_idx < len(class_list) else f"class_{class_idx}"

            if len(parts) == 5:
                # Standard YOLO detection: class_idx cx cy w h
                cx, cy, w, h = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
                xmin, ymin, xmax, ymax = denormalize_coords(cx, cy, w, h, img_w, img_h)
                annotation.boxes.append(BoundingBox(
                    class_name=class_name,
                    xmin=xmin, ymin=ymin, xmax=xmax, ymax=ymax,
                    annotation_type="bbox",
                ))
            else:
                # YOLOv8-seg: class_idx x1 y1 x2 y2 x3 y3 ...
                norm_points = []
                for i in range(1, len(parts) - 1, 2):
                    norm_points.append([float(parts[i]), float(parts[i + 1])])
                if len(norm_points) >= 3:
                    abs_points = denormalize_points(norm_points, img_w, img_h)
                    xmin, ymin, xmax, ymax = polygon_bounding_rect(abs_points)
                    annotation.boxes.append(BoundingBox(
                        class_name=class_name,
                        xmin=xmin, ymin=ymin, xmax=xmax, ymax=ymax,
                        annotation_type="polygon",
                        points=abs_points,
                    ))

        return annotation

    @staticmethod
    def write(annotation: ImageAnnotation, txt_path: Path, class_list: list[str]) -> None:
        lines = []
        for box in annotation.boxes:
            if box.class_name in class_list:
                class_idx = class_list.index(box.class_name)
            else:
                class_idx = len(class_list)
                class_list.append(box.class_name)

            if box.annotation_type == "polygon" and box.points:
                # YOLOv8-seg format: class_idx x1 y1 x2 y2 ...
                norm_pts = normalize_points(
                    box.points, annotation.image_width, annotation.image_height
                )
                coords = " ".join(f"{p[0]:.6f} {p[1]:.6f}" for p in norm_pts)
                lines.append(f"{class_idx} {coords}")
            else:
                # Standard YOLO detection format
                cx, cy, w, h = normalize_coords(
                    box.xmin, box.ymin, box.xmax, box.ymax,
                    annotation.image_width, annotation.image_height,
                )
                lines.append(f"{class_idx} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")

        txt_path.parent.mkdir(parents=True, exist_ok=True)
        txt_path.write_text("\n".join(lines) + "\n" if lines else "", encoding="utf-8")

    @staticmethod
    def write_classes_txt(class_list: list[str], folder: Path) -> None:
        path = folder / "classes.txt"
        path.write_text("\n".join(class_list) + "\n" if class_list else "", encoding="utf-8")

    @staticmethod
    def read_classes_txt(folder: Path) -> list[str]:
        path = folder / "classes.txt"
        if not path.exists():
            return []
        return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
