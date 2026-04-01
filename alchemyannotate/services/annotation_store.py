from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from alchemyannotate.models.annotation import ImageAnnotation


class AnnotationStore(QObject):
    """In-memory store for all image annotations with dirty tracking."""

    annotation_changed = Signal(str)  # emits filename

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._annotations: dict[str, ImageAnnotation] = {}
        self._dirty: set[str] = set()

    def get(self, filename: str) -> ImageAnnotation | None:
        return self._annotations.get(filename)

    def get_or_create(self, filename: str, img_w: int = 0, img_h: int = 0) -> ImageAnnotation:
        if filename not in self._annotations:
            self._annotations[filename] = ImageAnnotation(
                image_filename=filename,
                image_width=img_w,
                image_height=img_h,
            )
        return self._annotations[filename]

    def set(self, filename: str, annotation: ImageAnnotation) -> None:
        self._annotations[filename] = annotation
        self._dirty.add(filename)
        self.annotation_changed.emit(filename)

    def mark_dirty(self, filename: str) -> None:
        self._dirty.add(filename)
        self.annotation_changed.emit(filename)

    def mark_clean(self, filename: str) -> None:
        self._dirty.discard(filename)

    def dirty_files(self) -> set[str]:
        return set(self._dirty)

    def has_annotations(self, filename: str) -> bool:
        ann = self._annotations.get(filename)
        return ann is not None and len(ann.boxes) > 0

    def all_filenames(self) -> list[str]:
        return list(self._annotations.keys())

    def clear(self) -> None:
        self._annotations.clear()
        self._dirty.clear()
