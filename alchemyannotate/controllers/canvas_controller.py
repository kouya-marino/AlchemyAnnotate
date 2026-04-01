from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QPointF, QRectF, Signal

from alchemyannotate.models.annotation import BoundingBox
from alchemyannotate.utils.geometry import (
    qrectf_to_coords,
    clamp_box_to_image,
    clamp_points_to_image,
    polygon_bounding_rect,
)

if TYPE_CHECKING:
    from alchemyannotate.models.class_registry import ClassRegistry
    from alchemyannotate.services.annotation_store import AnnotationStore
    from alchemyannotate.views.canvas import AnnotationCanvas


class InteractionState(Enum):
    IDLE = auto()
    DRAWING = auto()
    DRAWING_POLYGON = auto()
    SELECTED = auto()


class CanvasController(QObject):
    """Manages draw/select/delete interactions on the canvas."""

    box_created = Signal(str)   # box_id
    box_deleted = Signal(str)   # box_id
    selection_changed = Signal(str)  # box_id or ""
    class_prompt_needed = Signal(QRectF)  # bbox drawn — needs class
    polygon_class_prompt_needed = Signal(list)  # polygon drawn — needs class (list of QPointF)

    def __init__(
        self,
        canvas: AnnotationCanvas,
        store: AnnotationStore,
        class_registry: ClassRegistry,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._canvas = canvas
        self._store = store
        self._registry = class_registry
        self._state = InteractionState.IDLE
        self._selected_box_id: str | None = None
        self._current_filename: str | None = None
        self._active_class: str = ""

        # Connect canvas signals
        self._canvas.box_drawn.connect(self._on_box_drawn)
        self._canvas.polygon_drawn.connect(self._on_polygon_drawn)
        self._canvas.box_selected.connect(self._on_box_selected)
        self._canvas.box_deselected.connect(self._on_box_deselected)

    @property
    def selected_box_id(self) -> str | None:
        return self._selected_box_id

    def set_current_image(self, filename: str | None) -> None:
        self._current_filename = filename
        self._selected_box_id = None
        self._state = InteractionState.IDLE

    def set_active_class(self, class_name: str) -> None:
        self._active_class = class_name
        color = self._registry.get_color(class_name)
        self._canvas.set_draw_color(color)

    def set_annotation_mode(self, mode: str) -> None:
        """Switch canvas between 'bbox' and 'polygon' drawing mode."""
        self._canvas.set_polygon_mode(mode == "polygon")

    def render_boxes(self, filename: str) -> None:
        """Render all annotations (boxes and polygons) for the given image."""
        ann = self._store.get(filename)
        if not ann:
            return
        for box in ann.boxes:
            color = self._registry.get_color(box.class_name)
            if box.annotation_type == "polygon" and box.points:
                points = [QPointF(p[0], p[1]) for p in box.points]
                self._canvas.add_polygon(box.id, points, color)
            else:
                rect = QRectF(box.xmin, box.ymin, box.width, box.height)
                self._canvas.add_box(box.id, rect, color)

    def delete_selected(self) -> None:
        """Delete the currently selected annotation."""
        if not self._selected_box_id or not self._current_filename:
            return

        ann = self._store.get(self._current_filename)
        if not ann:
            return

        ann.boxes = [b for b in ann.boxes if b.id != self._selected_box_id]
        self._store.mark_dirty(self._current_filename)
        self._canvas.remove_box(self._selected_box_id)

        deleted_id = self._selected_box_id
        self._selected_box_id = None
        self._state = InteractionState.IDLE
        self.box_deleted.emit(deleted_id)
        self.selection_changed.emit("")

    def change_box_class(self, box_id: str, new_class: str) -> None:
        """Change the class of an annotation."""
        if not self._current_filename:
            return
        ann = self._store.get(self._current_filename)
        if not ann:
            return
        for box in ann.boxes:
            if box.id == box_id:
                box.class_name = new_class
                self._store.mark_dirty(self._current_filename)
                color = self._registry.get_color(new_class)
                self._canvas.update_box_color(box_id, color)
                break

    def create_box(self, rect: QRectF, class_name: str) -> None:
        """Create a bounding box annotation."""
        if not self._current_filename:
            return

        ann = self._store.get_or_create(self._current_filename)
        if ann.image_width == 0:
            return

        xmin, ymin, xmax, ymax = qrectf_to_coords(rect)
        box = BoundingBox(
            class_name=class_name,
            xmin=xmin, ymin=ymin, xmax=xmax, ymax=ymax,
            annotation_type="bbox",
        )
        clamp_box_to_image(box, ann.image_width, ann.image_height)

        ann.boxes.append(box)
        self._store.mark_dirty(self._current_filename)

        color = self._registry.get_color(box.class_name)
        self._canvas.add_box(box.id, QRectF(box.xmin, box.ymin, box.width, box.height), color)

        self._selected_box_id = box.id
        self._state = InteractionState.SELECTED
        self._canvas.highlight_box(box.id)
        self.box_created.emit(box.id)
        self.selection_changed.emit(box.id)

    def create_polygon(self, points_qpf: list[QPointF], class_name: str) -> None:
        """Create a polygon annotation from a list of QPointF vertices."""
        if not self._current_filename:
            return

        ann = self._store.get_or_create(self._current_filename)
        if ann.image_width == 0:
            return

        raw_points = [[p.x(), p.y()] for p in points_qpf]
        clamped = clamp_points_to_image(raw_points, ann.image_width, ann.image_height)
        xmin, ymin, xmax, ymax = polygon_bounding_rect(clamped)

        box = BoundingBox(
            class_name=class_name,
            xmin=xmin, ymin=ymin, xmax=xmax, ymax=ymax,
            annotation_type="polygon",
            points=clamped,
        )

        ann.boxes.append(box)
        self._store.mark_dirty(self._current_filename)

        color = self._registry.get_color(box.class_name)
        canvas_points = [QPointF(p[0], p[1]) for p in clamped]
        self._canvas.add_polygon(box.id, canvas_points, color)

        self._selected_box_id = box.id
        self._state = InteractionState.SELECTED
        self._canvas.highlight_box(box.id)
        self.box_created.emit(box.id)
        self.selection_changed.emit(box.id)

    # -- Signal handlers --

    def _on_box_drawn(self, rect: QRectF) -> None:
        if not self._current_filename:
            return
        self.class_prompt_needed.emit(rect)

    def _on_polygon_drawn(self, points: list) -> None:
        if not self._current_filename:
            return
        self.polygon_class_prompt_needed.emit(points)

    def _on_box_selected(self, box_id: str) -> None:
        self._selected_box_id = box_id
        self._state = InteractionState.SELECTED
        self._canvas.highlight_box(box_id)
        self.selection_changed.emit(box_id)

    def _on_box_deselected(self) -> None:
        self._selected_box_id = None
        self._state = InteractionState.IDLE
        self._canvas.highlight_box(None)
        self.selection_changed.emit("")
