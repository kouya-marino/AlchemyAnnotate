from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QComboBox,
    QLabel,
)


class BoxListPanel(QWidget):
    """Panel listing bounding boxes for the current image."""

    box_highlight_requested = Signal(str)  # box_id
    box_delete_requested = Signal(str)     # box_id
    box_class_changed = Signal(str, str)   # box_id, new_class_name

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._header = QLabel("Boxes")
        self._header.setStyleSheet("font-weight: bold; padding: 4px;")
        layout.addWidget(self._header)

        self._list = QListWidget()
        self._list.currentItemChanged.connect(self._on_selection_changed)
        layout.addWidget(self._list)

        # Class edit row
        class_row = QHBoxLayout()
        class_row.addWidget(QLabel("Class:"))
        self._class_combo = QComboBox()
        self._class_combo.currentTextChanged.connect(self._on_class_combo_changed)
        class_row.addWidget(self._class_combo, stretch=1)
        layout.addLayout(class_row)

        # Delete button
        self._delete_btn = QPushButton("Delete Box")
        self._delete_btn.clicked.connect(self._on_delete_clicked)
        layout.addWidget(self._delete_btn)

        self._box_ids: list[str] = []
        self._updating = False

    def set_classes(self, class_names: list[str]) -> None:
        """Update the class combo box options."""
        self._updating = True
        self._class_combo.clear()
        self._class_combo.addItems(class_names)
        self._updating = False

    def set_boxes(self, boxes: list[dict]) -> None:
        """Populate box list. Each dict has: id, class_name, xmin, ymin, xmax, ymax."""
        self._updating = True
        self._list.clear()
        self._box_ids.clear()
        for b in boxes:
            label = f"{b['class_name']}: ({b['xmin']:.0f},{b['ymin']:.0f})-({b['xmax']:.0f},{b['ymax']:.0f})"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, b["id"])
            self._list.addItem(item)
            self._box_ids.append(b["id"])
        self._header.setText(f"Boxes ({len(boxes)})")
        self._updating = False

    def select_box(self, box_id: str | None) -> None:
        self._updating = True
        if box_id is None:
            self._list.clearSelection()
        else:
            for i in range(self._list.count()):
                item = self._list.item(i)
                if item and item.data(Qt.ItemDataRole.UserRole) == box_id:
                    self._list.setCurrentItem(item)
                    break
        self._updating = False

    def _current_box_id(self) -> str | None:
        item = self._list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _on_selection_changed(self, current: QListWidgetItem | None, _prev) -> None:
        if self._updating:
            return
        box_id = current.data(Qt.ItemDataRole.UserRole) if current else None
        if box_id:
            self.box_highlight_requested.emit(box_id)

    def _on_class_combo_changed(self, text: str) -> None:
        if self._updating or not text:
            return
        box_id = self._current_box_id()
        if box_id:
            self.box_class_changed.emit(box_id, text)

    def _on_delete_clicked(self) -> None:
        box_id = self._current_box_id()
        if box_id:
            self.box_delete_requested.emit(box_id)
