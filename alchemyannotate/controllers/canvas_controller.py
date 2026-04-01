from __future__ import annotations

from copy import deepcopy
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


class _UndoCommand:
    """Single undoable action."""

    def __init__(self, action: str, filename: str, box_before: dict | None, box_after: dict | None) -> None:
        self.action = action        # "create", "delete", "modify"
        self.filename = filename
        self.box_before = box_before  # BoundingBox.to_dict() or None
        self.box_after = box_after    # BoundingBox.to_dict() or None


class CanvasController(QObject):
    """Manages draw/select/delete interactions on the canvas."""

    box_created = Signal(str)   # box_id
    box_deleted = Signal(str)   # box_id
    box_modified = Signal(str)  # box_id — geometry or class changed
    selection_changed = Signal(str)  # box_id or ""
    class_prompt_needed = Signal(QRectF)
    polygon_class_prompt_needed = Signal(list)

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

        # Undo/redo stacks
        self._undo_stack: list[_UndoCommand] = []
        self._redo_stack: list[_UndoCommand] = []
        self._max_undo = 50

        # Clipboard for copy/paste
        self._clipboard: dict | None = None

        # Connect canvas signals
        self._canvas.box_drawn.connect(self._on_box_drawn)
        self._canvas.polygon_drawn.connect(self._on_polygon_drawn)
        self._canvas.box_selected.connect(self._on_box_selected)
        self._canvas.box_deselected.connect(self._on_box_deselected)
        self._canvas.box_geometry_changed.connect(self._on_box_geometry_changed)
        self._canvas.polygon_geometry_changed.connect(self._on_polygon_geometry_changed)
        self._canvas.context_delete_requested.connect(self._on_context_delete)
        self._canvas.context_edit_class_requested.connect(self._on_context_edit_class)
        self._canvas.context_copy_requested.connect(self._on_context_copy)

    @property
    def selected_box_id(self) -> str | None:
        return self._selected_box_id

    @property
    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    @property
    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    @property
    def has_clipboard(self) -> bool:
        return self._clipboard is not None

    def set_current_image(self, filename: str | None) -> None:
        self._current_filename = filename
        self._selected_box_id = None
        self._state = InteractionState.IDLE

    def set_active_class(self, class_name: str) -> None:
        self._active_class = class_name
        color = self._registry.get_color(class_name)
        self._canvas.set_draw_color(color)

    def set_annotation_mode(self, mode: str) -> None:
        self._canvas.set_polygon_mode(mode == "polygon")

    def render_boxes(self, filename: str) -> None:
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

    # -- Undo/Redo --

    def _push_undo(self, cmd: _UndoCommand) -> None:
        self._undo_stack.append(cmd)
        if len(self._undo_stack) > self._max_undo:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def _find_box(self, filename: str, box_id: str) -> BoundingBox | None:
        ann = self._store.get(filename)
        if not ann:
            return None
        for box in ann.boxes:
            if box.id == box_id:
                return box
        return None

    def undo(self) -> None:
        if not self._undo_stack:
            return
        cmd = self._undo_stack.pop()
        self._redo_stack.append(cmd)

        ann = self._store.get(cmd.filename)
        if not ann:
            return

        if cmd.action == "create":
            # Undo create → remove the box
            box_id = cmd.box_after["id"]
            ann.boxes = [b for b in ann.boxes if b.id != box_id]
            self._canvas.remove_box(box_id)
            if self._selected_box_id == box_id:
                self._selected_box_id = None
                self._state = InteractionState.IDLE
                self.selection_changed.emit("")

        elif cmd.action == "delete":
            # Undo delete → restore the box
            box = BoundingBox.from_dict(cmd.box_before)
            ann.boxes.append(box)
            self._render_single_box(box)

        elif cmd.action == "modify":
            # Undo modify → restore previous state
            box_id = cmd.box_before["id"]
            for i, b in enumerate(ann.boxes):
                if b.id == box_id:
                    ann.boxes[i] = BoundingBox.from_dict(cmd.box_before)
                    self._canvas.remove_box(box_id)
                    self._render_single_box(ann.boxes[i])
                    if self._selected_box_id == box_id:
                        self._canvas.highlight_box(box_id)
                    break

        self._store.mark_dirty(cmd.filename)
        self.box_modified.emit("")

    def redo(self) -> None:
        if not self._redo_stack:
            return
        cmd = self._redo_stack.pop()
        self._undo_stack.append(cmd)

        ann = self._store.get(cmd.filename)
        if not ann:
            return

        if cmd.action == "create":
            box = BoundingBox.from_dict(cmd.box_after)
            ann.boxes.append(box)
            self._render_single_box(box)

        elif cmd.action == "delete":
            box_id = cmd.box_before["id"]
            ann.boxes = [b for b in ann.boxes if b.id != box_id]
            self._canvas.remove_box(box_id)
            if self._selected_box_id == box_id:
                self._selected_box_id = None
                self._state = InteractionState.IDLE
                self.selection_changed.emit("")

        elif cmd.action == "modify":
            box_id = cmd.box_after["id"]
            for i, b in enumerate(ann.boxes):
                if b.id == box_id:
                    ann.boxes[i] = BoundingBox.from_dict(cmd.box_after)
                    self._canvas.remove_box(box_id)
                    self._render_single_box(ann.boxes[i])
                    if self._selected_box_id == box_id:
                        self._canvas.highlight_box(box_id)
                    break

        self._store.mark_dirty(cmd.filename)
        self.box_modified.emit("")

    def _render_single_box(self, box: BoundingBox) -> None:
        color = self._registry.get_color(box.class_name)
        if box.annotation_type == "polygon" and box.points:
            points = [QPointF(p[0], p[1]) for p in box.points]
            self._canvas.add_polygon(box.id, points, color)
        else:
            rect = QRectF(box.xmin, box.ymin, box.width, box.height)
            self._canvas.add_box(box.id, rect, color)

    # -- Copy/Paste --

    def copy_selected(self) -> None:
        if not self._selected_box_id or not self._current_filename:
            return
        box = self._find_box(self._current_filename, self._selected_box_id)
        if box:
            self._clipboard = box.to_dict()

    def copy_box(self, box_id: str) -> None:
        if not self._current_filename:
            return
        box = self._find_box(self._current_filename, box_id)
        if box:
            self._clipboard = box.to_dict()

    def paste(self) -> None:
        if not self._clipboard or not self._current_filename:
            return
        ann = self._store.get_or_create(self._current_filename)
        if ann.image_width == 0:
            return

        box = BoundingBox.from_dict(self._clipboard)
        # Generate new id and offset position
        import uuid
        box.id = uuid.uuid4().hex[:8]
        offset = 15.0
        box.xmin += offset
        box.ymin += offset
        box.xmax += offset
        box.ymax += offset
        if box.points:
            box.points = [[p[0] + offset, p[1] + offset] for p in box.points]
        clamp_box_to_image(box, ann.image_width, ann.image_height)
        if box.points:
            box.points = clamp_points_to_image(box.points, ann.image_width, ann.image_height)

        ann.boxes.append(box)
        self._store.mark_dirty(self._current_filename)

        self._render_single_box(box)

        self._push_undo(_UndoCommand("create", self._current_filename, None, box.to_dict()))

        self._selected_box_id = box.id
        self._state = InteractionState.SELECTED
        self._canvas.highlight_box(box.id)
        self.box_created.emit(box.id)
        self.selection_changed.emit(box.id)

    # -- CRUD operations --

    def delete_selected(self) -> None:
        if not self._selected_box_id or not self._current_filename:
            return

        ann = self._store.get(self._current_filename)
        if not ann:
            return

        # Save for undo
        box_dict = None
        for b in ann.boxes:
            if b.id == self._selected_box_id:
                box_dict = b.to_dict()
                break

        ann.boxes = [b for b in ann.boxes if b.id != self._selected_box_id]
        self._store.mark_dirty(self._current_filename)
        self._canvas.remove_box(self._selected_box_id)

        if box_dict:
            self._push_undo(_UndoCommand("delete", self._current_filename, box_dict, None))

        deleted_id = self._selected_box_id
        self._selected_box_id = None
        self._state = InteractionState.IDLE
        self.box_deleted.emit(deleted_id)
        self.selection_changed.emit("")

    def change_box_class(self, box_id: str, new_class: str) -> None:
        if not self._current_filename:
            return
        ann = self._store.get(self._current_filename)
        if not ann:
            return
        for box in ann.boxes:
            if box.id == box_id:
                old_dict = box.to_dict()
                box.class_name = new_class
                self._store.mark_dirty(self._current_filename)
                color = self._registry.get_color(new_class)
                self._canvas.update_box_color(box_id, color)
                self._push_undo(_UndoCommand("modify", self._current_filename, old_dict, box.to_dict()))
                break

    def create_box(self, rect: QRectF, class_name: str) -> None:
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

        self._push_undo(_UndoCommand("create", self._current_filename, None, box.to_dict()))

        self._selected_box_id = box.id
        self._state = InteractionState.SELECTED
        self._canvas.highlight_box(box.id)
        self.box_created.emit(box.id)
        self.selection_changed.emit(box.id)

    def create_polygon(self, points_qpf: list[QPointF], class_name: str) -> None:
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

        self._push_undo(_UndoCommand("create", self._current_filename, None, box.to_dict()))

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

    def _on_box_geometry_changed(self, box_id: str, new_rect: QRectF) -> None:
        if not self._current_filename:
            return
        ann = self._store.get(self._current_filename)
        if not ann:
            return
        for box in ann.boxes:
            if box.id == box_id:
                old_dict = box.to_dict()
                xmin, ymin, xmax, ymax = qrectf_to_coords(new_rect)
                box.xmin, box.ymin, box.xmax, box.ymax = xmin, ymin, xmax, ymax
                clamp_box_to_image(box, ann.image_width, ann.image_height)
                self._store.mark_dirty(self._current_filename)
                self._push_undo(_UndoCommand("modify", self._current_filename, old_dict, box.to_dict()))
                self.box_modified.emit(box_id)
                break

    def _on_polygon_geometry_changed(self, box_id: str, new_points: list) -> None:
        if not self._current_filename:
            return
        ann = self._store.get(self._current_filename)
        if not ann:
            return
        for box in ann.boxes:
            if box.id == box_id:
                old_dict = box.to_dict()
                box.points = clamp_points_to_image(new_points, ann.image_width, ann.image_height)
                box.compute_bbox_from_points()
                self._store.mark_dirty(self._current_filename)
                self._push_undo(_UndoCommand("modify", self._current_filename, old_dict, box.to_dict()))
                self.box_modified.emit(box_id)
                break

    def _on_context_delete(self, box_id: str) -> None:
        self._selected_box_id = box_id
        self.delete_selected()

    def _on_context_edit_class(self, box_id: str) -> None:
        self._selected_box_id = box_id
        self._state = InteractionState.SELECTED
        self._canvas.highlight_box(box_id)
        self.selection_changed.emit(box_id)

    def _on_context_copy(self, box_id: str) -> None:
        self.copy_box(box_id)
