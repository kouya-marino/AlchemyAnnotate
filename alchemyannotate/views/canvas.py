from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QRectF, QPointF
from PySide6.QtGui import (
    QPixmap, QPen, QColor, QBrush, QPainter, QWheelEvent, QMouseEvent,
    QPolygonF, QFont,
)
from PySide6.QtWidgets import (
    QGraphicsView,
    QGraphicsScene,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsPolygonItem,
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsSimpleTextItem,
    QMenu,
)


class BoxRectItem(QGraphicsRectItem):
    """A bounding box rectangle on the canvas."""

    def __init__(self, box_id: str, rect: QRectF, color: QColor) -> None:
        super().__init__(rect)
        self.box_id = box_id
        self._base_color = color
        pen = QPen(color, 2)
        pen.setCosmetic(True)
        self.setPen(pen)
        self.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable, True)

    def set_selected_style(self, selected: bool) -> None:
        pen = self.pen()
        pen.setWidth(4 if selected else 2)
        if selected:
            fill = QColor(self._base_color)
            fill.setAlpha(40)
            self.setBrush(QBrush(fill))
        else:
            self.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        self.setPen(pen)

    def update_color(self, color: QColor) -> None:
        self._base_color = color
        pen = self.pen()
        pen.setColor(color)
        self.setPen(pen)


class PolygonItem(QGraphicsPolygonItem):
    """A polygon annotation on the canvas."""

    def __init__(self, box_id: str, polygon: QPolygonF, color: QColor) -> None:
        super().__init__(polygon)
        self.box_id = box_id
        self._base_color = color
        pen = QPen(color, 2)
        pen.setCosmetic(True)
        self.setPen(pen)
        self.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        self.setFlag(QGraphicsPolygonItem.GraphicsItemFlag.ItemIsSelectable, True)

    def set_selected_style(self, selected: bool) -> None:
        pen = self.pen()
        pen.setWidth(4 if selected else 2)
        if selected:
            fill = QColor(self._base_color)
            fill.setAlpha(40)
            self.setBrush(QBrush(fill))
        else:
            self.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        self.setPen(pen)

    def update_color(self, color: QColor) -> None:
        self._base_color = color
        pen = self.pen()
        pen.setColor(color)
        self.setPen(pen)


class _HandleItem(QGraphicsRectItem):
    """Resize/vertex handle shown on selected annotations."""
    SIZE = 8

    def __init__(self, handle_id, parent_box_id: str) -> None:
        half = self.SIZE / 2
        super().__init__(-half, -half, self.SIZE, self.SIZE)
        self.handle_id = handle_id  # str for bbox ("tl","t",...), int for polygon vertex
        self.parent_box_id = parent_box_id
        self.setPen(QPen(QColor("white"), 1))
        self.setBrush(QBrush(QColor("#4363d8")))
        self.setZValue(100)
        self.setFlag(self.GraphicsItemFlag.ItemIgnoresTransformations, True)


class AnnotationCanvas(QGraphicsView):
    """Graphics view for displaying images and drawing annotations."""

    # Signals
    box_drawn = Signal(QRectF)
    polygon_drawn = Signal(list)
    box_selected = Signal(str)
    box_deselected = Signal()
    canvas_clicked = Signal()
    box_geometry_changed = Signal(str, QRectF)       # box_id, new rect
    polygon_geometry_changed = Signal(str, list)      # box_id, new points [[x,y],...]
    zoom_changed = Signal(float)                      # zoom percentage
    context_delete_requested = Signal(str)            # box_id
    context_edit_class_requested = Signal(str)        # box_id
    context_copy_requested = Signal(str)              # box_id

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        self._pixmap_item: QGraphicsPixmapItem | None = None
        self._box_items: dict[str, BoxRectItem | PolygonItem] = {}

        # Drawing state — bbox
        self._draw_enabled = True
        self._drawing = False
        self._draw_start: QPointF | None = None
        self._draw_rect_item: QGraphicsRectItem | None = None
        self._draw_color = QColor("#00ff00")

        # Drawing state — polygon
        self._polygon_mode = False
        self._drawing_polygon = False
        self._polygon_points: list[QPointF] = []
        self._polygon_preview_items: list = []

        # Resize/move state
        self._handles: list[_HandleItem] = []
        self._active_handle: _HandleItem | None = None
        self._moving = False
        self._move_start: QPointF | None = None
        self._move_box_id: str | None = None
        self._suppress_context_menu = False

        # Label items
        self._label_items: dict[str, QGraphicsSimpleTextItem] = {}
        self._labels_visible = False

        # View settings
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self._panning = False
        self._pan_start = QPointF()

    def set_image(self, pixmap: QPixmap) -> None:
        """Display a new image, clearing all items."""
        self._cancel_polygon_drawing()
        self._clear_handles()
        self._scene.clear()
        self._box_items.clear()
        self._label_items.clear()
        self._pixmap_item = self._scene.addPixmap(pixmap)
        self._scene.setSceneRect(QRectF(pixmap.rect()))
        self.fit_to_window()

    def fit_to_window(self) -> None:
        if self._pixmap_item:
            self.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
            self._emit_zoom()

    def clear_canvas(self) -> None:
        self._cancel_polygon_drawing()
        self._clear_handles()
        self._scene.clear()
        self._pixmap_item = None
        self._box_items.clear()
        self._label_items.clear()

    # -- Box management --

    def add_box(self, box_id: str, rect: QRectF, color: QColor) -> None:
        item = BoxRectItem(box_id, rect, color)
        self._scene.addItem(item)
        self._box_items[box_id] = item

    def add_polygon(self, box_id: str, points: list[QPointF], color: QColor) -> None:
        polygon = QPolygonF(points)
        item = PolygonItem(box_id, polygon, color)
        self._scene.addItem(item)
        self._box_items[box_id] = item

    def remove_box(self, box_id: str) -> None:
        item = self._box_items.pop(box_id, None)
        if item:
            self._scene.removeItem(item)
        label = self._label_items.pop(box_id, None)
        if label:
            self._scene.removeItem(label)
        if self._handles and self._handles[0].parent_box_id == box_id:
            self._clear_handles()

    def highlight_box(self, box_id: str | None) -> None:
        for bid, item in self._box_items.items():
            item.set_selected_style(bid == box_id)
        self._clear_handles()
        if box_id:
            self._show_handles(box_id)

    def update_box_color(self, box_id: str, color: QColor) -> None:
        item = self._box_items.get(box_id)
        if item:
            item.update_color(color)

    def update_box_rect(self, box_id: str, rect: QRectF) -> None:
        item = self._box_items.get(box_id)
        if isinstance(item, BoxRectItem):
            item.setRect(rect)

    def set_draw_color(self, color: QColor) -> None:
        self._draw_color = color

    def set_draw_enabled(self, enabled: bool) -> None:
        self._draw_enabled = enabled
        if not enabled:
            self._cancel_polygon_drawing()

    def set_polygon_mode(self, enabled: bool) -> None:
        if self._drawing_polygon:
            self._cancel_polygon_drawing()
        self._polygon_mode = enabled

    # -- Label management --

    def set_labels_visible(self, visible: bool) -> None:
        self._labels_visible = visible
        if not visible:
            for label in self._label_items.values():
                self._scene.removeItem(label)
            self._label_items.clear()

    def update_labels(self, box_labels: dict[str, str]) -> None:
        """Update all annotation labels. box_labels maps box_id -> class_name."""
        for label in self._label_items.values():
            self._scene.removeItem(label)
        self._label_items.clear()
        if not self._labels_visible:
            return
        for box_id, class_name in box_labels.items():
            item = self._box_items.get(box_id)
            if not item:
                continue
            if isinstance(item, BoxRectItem):
                pos = item.rect().topLeft() + QPointF(2, -16)
            elif isinstance(item, PolygonItem):
                br = item.boundingRect()
                pos = QPointF(br.left() + 2, br.top() - 16)
            else:
                continue
            text = QGraphicsSimpleTextItem(class_name)
            text.setPos(pos)
            text.setBrush(QBrush(QColor("yellow")))
            font = QFont()
            font.setPointSize(10)
            font.setBold(True)
            text.setFont(font)
            text.setZValue(50)
            self._scene.addItem(text)
            self._label_items[box_id] = text

    # -- Handle management --

    def _show_handles(self, box_id: str) -> None:
        item = self._box_items.get(box_id)
        if not item:
            return
        if isinstance(item, BoxRectItem):
            rect = item.rect()
            positions = {
                "tl": rect.topLeft(), "tr": rect.topRight(),
                "bl": rect.bottomLeft(), "br": rect.bottomRight(),
                "t": QPointF(rect.center().x(), rect.top()),
                "b": QPointF(rect.center().x(), rect.bottom()),
                "l": QPointF(rect.left(), rect.center().y()),
                "r": QPointF(rect.right(), rect.center().y()),
            }
            for hid, pos in positions.items():
                h = _HandleItem(hid, box_id)
                h.setPos(pos)
                self._scene.addItem(h)
                self._handles.append(h)
        elif isinstance(item, PolygonItem):
            polygon = item.polygon()
            for i in range(polygon.count()):
                h = _HandleItem(i, box_id)
                h.setPos(polygon.at(i))
                self._scene.addItem(h)
                self._handles.append(h)

    def _clear_handles(self) -> None:
        for h in self._handles:
            self._scene.removeItem(h)
        self._handles.clear()
        self._active_handle = None

    def _update_handle_positions(self) -> None:
        if not self._handles:
            return
        box_id = self._handles[0].parent_box_id
        item = self._box_items.get(box_id)
        if not item:
            return
        if isinstance(item, BoxRectItem):
            rect = item.rect()
            positions = {
                "tl": rect.topLeft(), "tr": rect.topRight(),
                "bl": rect.bottomLeft(), "br": rect.bottomRight(),
                "t": QPointF(rect.center().x(), rect.top()),
                "b": QPointF(rect.center().x(), rect.bottom()),
                "l": QPointF(rect.left(), rect.center().y()),
                "r": QPointF(rect.right(), rect.center().y()),
            }
            for h in self._handles:
                pos = positions.get(h.handle_id)
                if pos:
                    h.setPos(pos)
        elif isinstance(item, PolygonItem):
            polygon = item.polygon()
            for h in self._handles:
                if isinstance(h.handle_id, int) and h.handle_id < polygon.count():
                    h.setPos(polygon.at(h.handle_id))

    # -- Polygon drawing helpers --

    def _add_polygon_vertex(self, scene_pos: QPointF) -> None:
        self._polygon_points.append(scene_pos)
        self._drawing_polygon = True

        dot_size = 6
        pen = QPen(self._draw_color, 1)
        pen.setCosmetic(True)
        brush = QBrush(self._draw_color)
        dot = self._scene.addEllipse(
            scene_pos.x() - dot_size / 2, scene_pos.y() - dot_size / 2,
            dot_size, dot_size, pen, brush,
        )
        self._polygon_preview_items.append(dot)

        if len(self._polygon_points) >= 2:
            prev = self._polygon_points[-2]
            line_pen = QPen(self._draw_color, 2, Qt.PenStyle.DashLine)
            line_pen.setCosmetic(True)
            line = self._scene.addLine(
                prev.x(), prev.y(), scene_pos.x(), scene_pos.y(), line_pen,
            )
            self._polygon_preview_items.append(line)

    def _finish_polygon(self) -> None:
        if len(self._polygon_points) >= 3:
            points = list(self._polygon_points)
            self._clear_polygon_preview()
            self._polygon_points.clear()
            self._drawing_polygon = False
            self.polygon_drawn.emit(points)
        else:
            self._cancel_polygon_drawing()

    def _cancel_polygon_drawing(self) -> None:
        self._clear_polygon_preview()
        self._polygon_points.clear()
        self._drawing_polygon = False

    def _clear_polygon_preview(self) -> None:
        for item in self._polygon_preview_items:
            self._scene.removeItem(item)
        self._polygon_preview_items.clear()

    # -- Mouse events --

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self._pan_start = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return

        if event.button() == Qt.MouseButton.RightButton:
            if self._drawing_polygon:
                self._cancel_polygon_drawing()
                self._suppress_context_menu = True
                event.accept()
                return

        if event.button() == Qt.MouseButton.LeftButton:
            view_pos = event.position().toPoint()
            scene_pos = self.mapToScene(view_pos)
            items_at = self.items(view_pos)

            # Polygon vertex placement (mid-drawing)
            if self._drawing_polygon:
                if self._pixmap_item and self._pixmap_item.contains(scene_pos):
                    self._add_polygon_vertex(scene_pos)
                event.accept()
                return

            # Check if clicking on a resize/vertex handle
            for it in items_at:
                if isinstance(it, _HandleItem):
                    self._active_handle = it
                    self._move_start = scene_pos
                    event.accept()
                    return

            # Check if clicking on an existing annotation
            for it in items_at:
                if isinstance(it, (BoxRectItem, PolygonItem)):
                    if self._handles and self._handles[0].parent_box_id == it.box_id:
                        # Already selected — start move
                        self._moving = True
                        self._move_start = scene_pos
                        self._move_box_id = it.box_id
                    else:
                        # Select it
                        self.highlight_box(it.box_id)
                        self.box_selected.emit(it.box_id)
                    event.accept()
                    return

            if not self._draw_enabled:
                self.highlight_box(None)
                self.box_deselected.emit()
                self.canvas_clicked.emit()
                super().mousePressEvent(event)
                return

            # On the image? Start drawing
            if self._pixmap_item and self._pixmap_item.contains(scene_pos):
                if self._polygon_mode:
                    self._add_polygon_vertex(scene_pos)
                    event.accept()
                    return
                else:
                    self._drawing = True
                    self._draw_start = scene_pos
                    pen = QPen(self._draw_color, 2, Qt.PenStyle.DashLine)
                    pen.setCosmetic(True)
                    self._draw_rect_item = self._scene.addRect(
                        QRectF(scene_pos, scene_pos), pen
                    )
                    event.accept()
                    return

            # Click on empty area
            self.highlight_box(None)
            self.box_deselected.emit()
            self.canvas_clicked.emit()

        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._drawing_polygon:
            self._finish_polygon()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._panning:
            delta = event.position() - self._pan_start
            self._pan_start = event.position()
            self.horizontalScrollBar().setValue(
                int(self.horizontalScrollBar().value() - delta.x())
            )
            self.verticalScrollBar().setValue(
                int(self.verticalScrollBar().value() - delta.y())
            )
            event.accept()
            return

        if self._drawing and self._draw_start and self._draw_rect_item:
            scene_pos = self.mapToScene(event.position().toPoint())
            rect = QRectF(self._draw_start, scene_pos).normalized()
            self._draw_rect_item.setRect(rect)
            event.accept()
            return

        # Handle resize / vertex drag
        if self._active_handle and self._move_start:
            scene_pos = self.mapToScene(event.position().toPoint())
            box_id = self._active_handle.parent_box_id
            item = self._box_items.get(box_id)

            if isinstance(item, BoxRectItem) and isinstance(self._active_handle.handle_id, str):
                rect = QRectF(item.rect())
                hid = self._active_handle.handle_id
                if "t" in hid:
                    rect.setTop(min(scene_pos.y(), rect.bottom() - 3))
                if "b" in hid:
                    rect.setBottom(max(scene_pos.y(), rect.top() + 3))
                if "l" in hid:
                    rect.setLeft(min(scene_pos.x(), rect.right() - 3))
                if "r" in hid:
                    rect.setRight(max(scene_pos.x(), rect.left() + 3))
                item.setRect(rect)
                self._update_handle_positions()

            elif isinstance(item, PolygonItem) and isinstance(self._active_handle.handle_id, int):
                polygon = QPolygonF(item.polygon())
                idx = self._active_handle.handle_id
                if 0 <= idx < polygon.count():
                    polygon[idx] = scene_pos
                    item.setPolygon(polygon)
                    self._update_handle_positions()

            event.accept()
            return

        # Handle box/polygon move
        if self._moving and self._move_start and self._move_box_id:
            scene_pos = self.mapToScene(event.position().toPoint())
            delta = scene_pos - self._move_start
            item = self._box_items.get(self._move_box_id)
            if isinstance(item, BoxRectItem):
                rect = item.rect()
                rect.translate(delta)
                item.setRect(rect)
            elif isinstance(item, PolygonItem):
                polygon = item.polygon()
                translated = QPolygonF()
                for i in range(polygon.count()):
                    translated.append(polygon.at(i) + delta)
                item.setPolygon(translated)
            self._move_start = scene_pos
            self._update_handle_positions()
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.MiddleButton and self._panning:
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            # End bbox drawing
            if self._drawing:
                self._drawing = False
                if self._draw_rect_item:
                    rect = self._draw_rect_item.rect().normalized()
                    self._scene.removeItem(self._draw_rect_item)
                    self._draw_rect_item = None
                    if rect.width() > 3 and rect.height() > 3:
                        self.box_drawn.emit(rect)
                self._draw_start = None
                event.accept()
                return

            # End handle drag (resize or vertex)
            if self._active_handle:
                box_id = self._active_handle.parent_box_id
                item = self._box_items.get(box_id)
                if isinstance(item, BoxRectItem):
                    self.box_geometry_changed.emit(box_id, item.rect())
                elif isinstance(item, PolygonItem):
                    polygon = item.polygon()
                    points = [[polygon.at(i).x(), polygon.at(i).y()]
                              for i in range(polygon.count())]
                    self.polygon_geometry_changed.emit(box_id, points)
                self._active_handle = None
                self._move_start = None
                event.accept()
                return

            # End move
            if self._moving:
                self._moving = False
                box_id = self._move_box_id
                item = self._box_items.get(box_id) if box_id else None
                if isinstance(item, BoxRectItem):
                    self.box_geometry_changed.emit(box_id, item.rect())
                elif isinstance(item, PolygonItem):
                    polygon = item.polygon()
                    points = [[polygon.at(i).x(), polygon.at(i).y()]
                              for i in range(polygon.count())]
                    self.polygon_geometry_changed.emit(box_id, points)
                self._move_start = None
                self._move_box_id = None
                event.accept()
                return

        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event) -> None:
        if self._suppress_context_menu:
            self._suppress_context_menu = False
            return
        items_at = self.items(event.pos())
        for it in items_at:
            if isinstance(it, (BoxRectItem, PolygonItem)):
                menu = QMenu(self)
                edit_action = menu.addAction("Edit Class")
                copy_action = menu.addAction("Copy Annotation")
                menu.addSeparator()
                delete_action = menu.addAction("Delete")
                action = menu.exec(event.globalPos())
                if action == delete_action:
                    self.context_delete_requested.emit(it.box_id)
                elif action == edit_action:
                    self.context_edit_class_requested.emit(it.box_id)
                elif action == copy_action:
                    self.context_copy_requested.emit(it.box_id)
                event.accept()
                return
        super().contextMenuEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape and self._drawing_polygon:
            self._cancel_polygon_drawing()
            event.accept()
            return
        super().keyPressEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else 1.0 / 1.15
            self.scale(factor, factor)
            self._emit_zoom()
            event.accept()
        else:
            super().wheelEvent(event)

    def _emit_zoom(self) -> None:
        zoom = self.transform().m11() * 100
        self.zoom_changed.emit(zoom)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
