from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPixmap, QIcon
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QPushButton,
    QLabel,
)


class ClassPanel(QWidget):
    """Panel for managing annotation classes."""

    class_added = Signal(str)
    class_deleted = Signal(str)
    active_class_changed = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._header = QLabel("Classes")
        self._header.setStyleSheet("font-weight: bold; padding: 4px;")
        layout.addWidget(self._header)

        self._list = QListWidget()
        self._list.currentItemChanged.connect(self._on_selection_changed)
        layout.addWidget(self._list)

        # Add class row
        add_row = QHBoxLayout()
        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("New class name...")
        self._name_input.returnPressed.connect(self._on_add_clicked)
        add_row.addWidget(self._name_input, stretch=1)
        self._add_btn = QPushButton("Add")
        self._add_btn.clicked.connect(self._on_add_clicked)
        add_row.addWidget(self._add_btn)
        layout.addLayout(add_row)

        # Delete button
        self._delete_btn = QPushButton("Delete Class")
        self._delete_btn.clicked.connect(self._on_delete_clicked)
        layout.addWidget(self._delete_btn)

        self._active_class: str = ""

    @property
    def active_class(self) -> str:
        return self._active_class

    def set_classes(self, classes: list[tuple[str, QColor]]) -> None:
        """Populate list. Each tuple is (class_name, color)."""
        self._list.clear()
        for name, color in classes:
            self._add_item(name, color)
        self._header.setText(f"Classes ({len(classes)})")

    def add_class_item(self, name: str, color: QColor) -> None:
        self._add_item(name, color)
        self._header.setText(f"Classes ({self._list.count()})")

    def remove_class_item(self, name: str) -> None:
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == name:
                self._list.takeItem(i)
                break
        self._header.setText(f"Classes ({self._list.count()})")

    def _add_item(self, name: str, color: QColor) -> None:
        pm = QPixmap(12, 12)
        pm.fill(color)
        item = QListWidgetItem(QIcon(pm), name)
        item.setData(Qt.ItemDataRole.UserRole, name)
        self._list.addItem(item)

    def _on_selection_changed(self, current: QListWidgetItem | None, _prev) -> None:
        if current:
            name = current.data(Qt.ItemDataRole.UserRole)
            if name:
                self._active_class = name
                self.active_class_changed.emit(name)

    def _on_add_clicked(self) -> None:
        name = self._name_input.text().strip()
        if name:
            self._name_input.clear()
            self.class_added.emit(name)

    def _on_delete_clicked(self) -> None:
        item = self._list.currentItem()
        if item:
            name = item.data(Qt.ItemDataRole.UserRole)
            if name:
                self.class_deleted.emit(name)
