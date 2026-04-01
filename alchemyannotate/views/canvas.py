from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QRectF, QPointF
from PySide6.QtGui import (
    QPixmap, QPen, QColor, QBrush, QPainter, QWheelEvent, QMouseEvent,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QGraphicsView,
    QGraphicsScene,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsPolygonItem,
    QGraphicsEllipseItem,
    QGraphicsLineItem,
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
            pen.setStyle(Qt.PenStyle.SolidLine)
            fill = QColor(self._base_color)
            fill.setAlpha(40)
            self.setBrush(QBrush(fill))
        else:
            pen.setStyle(Qt.PenStyle.SolidLine)
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


class AnnotationCanvas(QGraphicsView):
    """Graphics view for displaying images and drawing bounding boxes and polygons."""

    box_drawn = Signal(QRectF)           # emitted when user finishes drawing a box
    polygon_drawn = Signal(list)         # emitted with list of QPointF when polygon is closed
    box_selected = Signal(str)           # emitted with box_id
    box_deselected = Signal()
    canvas_clicked = Signal()            # generic click (for deselection)

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
        self._scene.clear()
        self._box_items.clear()
        self._pixmap_item = self._scene.addPixmap(pixmap)
        self._scene.setSceneRect(QRectF(pixmap.rect()))
        self.fit_to_window()

    def fit_to_window(self) -> None:
        if self._pixmap_item:
            self.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def clear_canvas(self) -> None:
        self._cancel_polygon_drawing()
        self._scene.clear()
        self._pixmap_item = None
        self._box_items.clear()

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

    def highlight_box(self, box_id: str | None) -> None:
        for bid, item in self._box_items.items():
            item.set_selected_style(bid == box_id)

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
        """Switch between bbox and polygon drawing mode."""
        if self._drawing_polygon:
            self._cancel_polygon_drawing()
        self._polygon_mode = enabled

    # -- Polygon drawing helpers --

    def _add_polygon_vertex(self, scene_pos: QPointF) -> None:
        """Add a vertex to the polygon being drawn."""
        self._polygon_points.append(scene_pos)
        self._drawing_polygon = True

        # Draw vertex dot
        dot_size = 6
        pen = QPen(self._draw_color, 1)
        pen.setCosmetic(True)
        brush = QBrush(self._draw_color)
        dot = self._scene.addEllipse(
            scene_pos.x() - dot_size / 2, scene_pos.y() - dot_size / 2,
            dot_size, dot_size, pen, brush,
        )
        self._polygon_preview_items.append(dot)

        # Draw line from previous vertex
        if len(self._polygon_points) >= 2:
            prev = self._polygon_points[-2]
            line_pen = QPen(self._draw_color, 2, Qt.PenStyle.DashLine)
            line_pen.setCosmetic(True)
            line = self._scene.addLine(
                prev.x(), prev.y(), scene_pos.x(), scene_pos.y(), line_pen,
            )
            self._polygon_preview_items.append(line)

    def _finish_polygon(self) -> None:
        """Close the polygon and emit signal."""
        if len(self._polygon_points) >= 3:
            points = list(self._polygon_points)
            self._clear_polygon_preview()
            self._polygon_points.clear()
            self._drawing_polygon = False
            self.polygon_drawn.emit(points)
        else:
            self._cancel_polygon_drawing()

    def _cancel_polygon_drawing(self) -> None:
        """Cancel the current polygon drawing."""
        self._clear_polygon_preview()
        self._polygon_points.clear()
        self._drawing_polygon = False

    def _clear_polygon_preview(self) -> None:
        """Remove all temporary polygon preview items."""
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
                event.accept()
                return

        if event.button() == Qt.MouseButton.LeftButton:
            scene_pos = self.mapToScene(event.position().toPoint())

            # Check if clicking on an existing annotation (box or polygon)
            if not self._drawing_polygon:
                items = self._scene.items(scene_pos)
                for item in items:
                    if isinstance(item, (BoxRectItem, PolygonItem)):
                        self.highlight_box(item.box_id)
                        self.box_selected.emit(item.box_id)
                        event.accept()
                        return

            if not self._draw_enabled:
                if not self._drawing_polygon:
                    self.highlight_box(None)
                    self.box_deselected.emit()
                    self.canvas_clicked.emit()
                super().mousePressEvent(event)
                return

            # On the image?
            if self._pixmap_item and self._pixmap_item.contains(scene_pos):
                if self._polygon_mode:
                    # Polygon mode: place vertex
                    self._add_polygon_vertex(scene_pos)
                    event.accept()
                    return
                else:
                    # Bbox mode: start drag
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
            if not self._drawing_polygon:
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

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.MiddleButton and self._panning:
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton and self._drawing:
            self._drawing = False
            if self._draw_rect_item:
                rect = self._draw_rect_item.rect().normalized()
                self._scene.removeItem(self._draw_rect_item)
                self._draw_rect_item = None
                # Only emit if box has meaningful size
                if rect.width() > 3 and rect.height() > 3:
                    self.box_drawn.emit(rect)
            self._draw_start = None
            event.accept()
            return

        super().mouseReleaseEvent(event)

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
            event.accept()
        else:
            super().wheelEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
