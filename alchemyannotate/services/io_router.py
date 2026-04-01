from __future__ import annotations

from pathlib import Path

from alchemyannotate.models.annotation import ImageAnnotation
from alchemyannotate.services.io_coco import CocoIO
from alchemyannotate.services.io_voc import VocIO
from alchemyannotate.services.io_yolo import YoloIO
from alchemyannotate.utils.constants import ANNOTATION_FOLDER_NAMES, AnnotationFormat


class IORouter:
    """Dispatches read/write to the correct IO module based on format."""

    def __init__(self, base_folder: Path, fmt: AnnotationFormat) -> None:
        self._base_folder = base_folder
        self._format = fmt

    @property
    def format(self) -> AnnotationFormat:
        return self._format

    @format.setter
    def format(self, fmt: AnnotationFormat) -> None:
        self._format = fmt

    def annotation_folder(self, fmt: AnnotationFormat | None = None) -> Path:
        fmt = fmt or self._format
        return self._base_folder / ANNOTATION_FOLDER_NAMES[fmt]

    def save_annotation(
        self,
        annotation: ImageAnnotation,
        class_list: list[str],
    ) -> None:
        """Save a single image's annotations in the current format."""
        folder = self.annotation_folder()
        folder.mkdir(parents=True, exist_ok=True)

        stem = Path(annotation.image_filename).stem

        if self._format == AnnotationFormat.YOLO:
            YoloIO.write(annotation, folder / f"{stem}.txt", class_list)
            YoloIO.write_classes_txt(class_list, folder)
        elif self._format == AnnotationFormat.VOC:
            VocIO.write(annotation, folder / f"{stem}.xml")
        elif self._format == AnnotationFormat.COCO:
            # COCO writes all annotations to one file — handled by save_all
            pass

    def save_all(
        self,
        annotations: dict[str, ImageAnnotation],
        class_list: list[str],
    ) -> None:
        """Save all annotations."""
        folder = self.annotation_folder()
        folder.mkdir(parents=True, exist_ok=True)

        if self._format == AnnotationFormat.COCO:
            CocoIO.write_all(annotations, folder / "annotations.json", class_list)
        else:
            for annotation in annotations.values():
                self.save_annotation(annotation, class_list)

    def load_annotation(
        self,
        filename: str,
        img_w: int,
        img_h: int,
        class_list: list[str],
    ) -> ImageAnnotation | None:
        """Load annotations for a single image from disk."""
        folder = self.annotation_folder()
        stem = Path(filename).stem

        if self._format == AnnotationFormat.YOLO:
            txt_path = folder / f"{stem}.txt"
            if txt_path.exists():
                ann = YoloIO.read(txt_path, img_w, img_h, class_list)
                ann.image_filename = filename
                return ann
        elif self._format == AnnotationFormat.VOC:
            xml_path = folder / f"{stem}.xml"
            if xml_path.exists():
                ann = VocIO.read(xml_path)
                ann.image_filename = filename
                return ann
        elif self._format == AnnotationFormat.COCO:
            # COCO loads all at once
            json_path = folder / "annotations.json"
            if json_path.exists():
                all_anns = CocoIO.read_all(json_path, class_list)
                return all_anns.get(filename)
        return None

    def load_all(self, image_list: list[str], image_sizes: dict[str, tuple[int, int]], class_list: list[str]) -> dict[str, ImageAnnotation]:
        """Load all annotations for the current format."""
        folder = self.annotation_folder()
        if not folder.exists():
            return {}

        if self._format == AnnotationFormat.COCO:
            json_path = folder / "annotations.json"
            if json_path.exists():
                return CocoIO.read_all(json_path, class_list)
            return {}

        result: dict[str, ImageAnnotation] = {}
        for filename in image_list:
            stem = Path(filename).stem
            if self._format == AnnotationFormat.YOLO:
                txt_path = folder / f"{stem}.txt"
                if txt_path.exists():
                    img_w, img_h = image_sizes.get(filename, (0, 0))
                    ann = YoloIO.read(txt_path, img_w, img_h, class_list)
                    ann.image_filename = filename
                    result[filename] = ann
            elif self._format == AnnotationFormat.VOC:
                xml_path = folder / f"{stem}.xml"
                if xml_path.exists():
                    ann = VocIO.read(xml_path)
                    ann.image_filename = filename
                    result[filename] = ann
        return result

    @staticmethod
    def detect_existing_formats(base_folder: Path) -> list[AnnotationFormat]:
        """Check which annotation folders exist and contain files."""
        found = []
        for fmt, folder_name in ANNOTATION_FOLDER_NAMES.items():
            folder = base_folder / folder_name
            if folder.exists() and any(folder.iterdir()):
                found.append(fmt)
        return found
