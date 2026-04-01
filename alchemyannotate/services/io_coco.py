from __future__ import annotations

import json
from pathlib import Path

from alchemyannotate.models.annotation import BoundingBox, ImageAnnotation


class CocoIO:
    """Read/write COCO JSON annotation format with polygon support."""

    @staticmethod
    def read_all(json_path: Path, class_list: list[str]) -> dict[str, ImageAnnotation]:
        """Read all annotations from a COCO JSON file."""
        if not json_path.exists():
            return {}

        data = json.loads(json_path.read_text(encoding="utf-8"))

        # Build category map: id -> name
        cat_map: dict[int, str] = {}
        for cat in data.get("categories", []):
            cat_map[cat["id"]] = cat["name"]

        # Build image map: id -> {filename, width, height}
        img_map: dict[int, dict] = {}
        for img in data.get("images", []):
            img_map[img["id"]] = {
                "file_name": img["file_name"],
                "width": img.get("width", 0),
                "height": img.get("height", 0),
            }

        # Build annotations per image
        result: dict[str, ImageAnnotation] = {}
        for img_id, img_info in img_map.items():
            fname = img_info["file_name"]
            result[fname] = ImageAnnotation(
                image_filename=fname,
                image_width=img_info["width"],
                image_height=img_info["height"],
            )

        for ann in data.get("annotations", []):
            img_id = ann["image_id"]
            img_info = img_map.get(img_id)
            if not img_info:
                continue
            fname = img_info["file_name"]
            cat_name = cat_map.get(ann["category_id"], "unknown")
            bbox = ann.get("bbox", [0, 0, 0, 0])  # COCO: [x, y, width, height]
            x, y, w, h = bbox[0], bbox[1], bbox[2], bbox[3]

            # Check for polygon segmentation
            segmentation = ann.get("segmentation", [])
            if segmentation and isinstance(segmentation, list) and len(segmentation) > 0:
                flat = segmentation[0]
                if isinstance(flat, list) and len(flat) >= 6:
                    # Parse flat [x1, y1, x2, y2, ...] into [[x, y], ...]
                    points = [[flat[i], flat[i + 1]] for i in range(0, len(flat), 2)]
                    result[fname].boxes.append(BoundingBox(
                        class_name=cat_name,
                        xmin=x, ymin=y, xmax=x + w, ymax=y + h,
                        annotation_type="polygon",
                        points=points,
                    ))
                    continue

            # Bbox annotation
            result[fname].boxes.append(BoundingBox(
                class_name=cat_name,
                xmin=x, ymin=y, xmax=x + w, ymax=y + h,
                annotation_type="bbox",
            ))

        # Update class_list with any classes found in the file
        for cat_name in cat_map.values():
            if cat_name not in class_list:
                class_list.append(cat_name)

        return result

    @staticmethod
    def write_all(
        annotations: dict[str, ImageAnnotation],
        json_path: Path,
        class_list: list[str],
    ) -> None:
        """Write all annotations to a COCO JSON file."""
        # Build categories
        categories = []
        for i, name in enumerate(class_list):
            categories.append({"id": i + 1, "name": name, "supercategory": ""})

        class_to_id = {name: i + 1 for i, name in enumerate(class_list)}

        # Build images and annotations
        images = []
        coco_anns = []
        ann_id = 1

        for img_id, (fname, annotation) in enumerate(sorted(annotations.items()), start=1):
            images.append({
                "id": img_id,
                "file_name": fname,
                "width": annotation.image_width,
                "height": annotation.image_height,
            })

            for box in annotation.boxes:
                cat_id = class_to_id.get(box.class_name, 0)
                if cat_id == 0:
                    new_id = len(categories) + 1
                    categories.append({"id": new_id, "name": box.class_name, "supercategory": ""})
                    class_to_id[box.class_name] = new_id
                    cat_id = new_id

                w = box.xmax - box.xmin
                h = box.ymax - box.ymin

                coco_ann = {
                    "id": ann_id,
                    "image_id": img_id,
                    "category_id": cat_id,
                    "bbox": [round(box.xmin, 2), round(box.ymin, 2), round(w, 2), round(h, 2)],
                    "area": round(w * h, 2),
                    "iscrowd": 0,
                }

                # Add polygon segmentation if present
                if box.annotation_type == "polygon" and box.points:
                    flat = []
                    for pt in box.points:
                        flat.extend([round(pt[0], 2), round(pt[1], 2)])
                    coco_ann["segmentation"] = [flat]
                else:
                    coco_ann["segmentation"] = []

                coco_anns.append(coco_ann)
                ann_id += 1

        coco_data = {
            "images": images,
            "annotations": coco_anns,
            "categories": categories,
        }

        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(coco_data, indent=2), encoding="utf-8")
