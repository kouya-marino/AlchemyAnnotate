from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import QWidget, QVBoxLayout, QListWidget, QListWidgetItem, QLabel


def _dot_icon(color: str, size: int = 12) -> QIcon:
    """Create a small colored dot icon."""
    pm = QPixmap(size, size)
    pm.fill(QColor(color))
    return QIcon(pm)


_ICON_LABELED = None
_ICON_UNLABELED = None


def _get_icons() -> tuple[QIcon, QIcon]:
    global _ICON_LABELED, _ICON_UNLABELED
    if _ICON_LABELED is None:
        _ICON_LABELED = _dot_icon("#4caf50")
        _ICON_UNLABELED = _dot_icon("#9e9e9e")
    return _ICON_LABELED, _ICON_UNLABELED


class ImageSidebar(QWidget):
    """Sidebar listing all images in the folder with labeled/unlabeled status."""

    image_selected = Signal(str)  # emits filename

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._header = QLabel("Images")
        self._header.setStyleSheet("font-weight: bold; padding: 4px;")
        layout.addWidget(self._header)

        self._list = QListWidget()
        self._list.itemClicked.connect(self._on_item_clicked)
        self._list.itemDoubleClicked.connect(self._on_item_clicked)
        layout.addWidget(self._list)

        self._filenames: list[str] = []

    def set_images(self, filenames: list[str]) -> None:
        """Populate the list with image filenames."""
        self._filenames = filenames
        self._list.clear()
        icon_labeled, icon_unlabeled = _get_icons()
        for name in filenames:
            item = QListWidgetItem(icon_unlabeled, name)
            item.setData(Qt.ItemDataRole.UserRole, name)
            self._list.addItem(item)
        self._header.setText(f"Images ({len(filenames)})")

    def update_status(self, filename: str, has_annotations: bool) -> None:
        """Update the icon for a single image."""
        icon_labeled, icon_unlabeled = _get_icons()
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == filename:
                item.setIcon(icon_labeled if has_annotations else icon_unlabeled)
                break

    def select_image(self, filename: str) -> None:
        """Programmatically select an image in the list."""
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == filename:
                self._list.setCurrentItem(item)
                break

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        filename = item.data(Qt.ItemDataRole.UserRole)
        if filename:
            self.image_selected.emit(filename)
