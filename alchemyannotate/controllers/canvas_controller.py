from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QRectF, Signal

from alchemyannotate.models.annotation import BoundingBox
from alchemyannotate.utils.geometry import qrectf_to_coords, clamp_box_to_image

if TYPE_CHECKING:
    from alchemyannotate.models.class_registry import ClassRegistry
    from alchemyannotate.services.annotation_store import AnnotationStore
    from alchemyannotate.views.canvas import AnnotationCanvas


class InteractionState(Enum):
    IDLE = auto()
    DRAWING = auto()
    SELECTED = auto()


class CanvasController(QObject):
    """Manages draw/select/delete interactions on the canvas."""

    box_created = Signal(str)   # box_id
    box_deleted = Signal(str)   # box_id
    selection_changed = Signal(str)  # box_id or ""

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

    def render_boxes(self, filename: str) -> None:
        """Render all boxes for the given image on the canvas."""
        ann = self._store.get(filename)
        if not ann:
            return
        for box in ann.boxes:
            color = self._registry.get_color(box.class_name)
            rect = QRectF(box.xmin, box.ymin, box.width, box.height)
            self._canvas.add_box(box.id, rect, color)

    def delete_selected(self) -> None:
        """Delete the currently selected box."""
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
        """Change the class of a box."""
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

    def _on_box_drawn(self, rect: QRectF) -> None:
        if not self._current_filename:
            return

        ann = self._store.get_or_create(self._current_filename)
        if ann.image_width == 0:
            return

        xmin, ymin, xmax, ymax = qrectf_to_coords(rect)
        class_name = self._active_class or (self._registry.classes[0] if self._registry.classes else "object")

        box = BoundingBox(
            class_name=class_name,
            xmin=xmin, ymin=ymin, xmax=xmax, ymax=ymax,
        )
        clamp_box_to_image(box, ann.image_width, ann.image_height)

        ann.boxes.append(box)
        self._store.mark_dirty(self._current_filename)

        color = self._registry.get_color(box.class_name)
        self._canvas.add_box(box.id, QRectF(box.xmin, box.ymin, box.width, box.height), color)

        # Select the newly created box
        self._selected_box_id = box.id
        self._state = InteractionState.SELECTED
        self._canvas.highlight_box(box.id)
        self.box_created.emit(box.id)
        self.selection_changed.emit(box.id)

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
