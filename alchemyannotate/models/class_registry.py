from __future__ import annotations

from PySide6.QtGui import QColor

from alchemyannotate.utils.constants import COLOR_PALETTE


class ClassRegistry:
    """Manages annotation class names with auto-assigned colors."""

    def __init__(self, classes: list[str] | None = None) -> None:
        self._classes: list[str] = []
        self._colors: dict[str, QColor] = {}
        for name in classes or []:
            self.add_class(name)

    @property
    def classes(self) -> list[str]:
        return list(self._classes)

    def __len__(self) -> int:
        return len(self._classes)

    def add_class(self, name: str) -> QColor:
        """Add a class and return its assigned color. No-op if already exists."""
        if name in self._colors:
            return self._colors[name]
        color = QColor(COLOR_PALETTE[len(self._classes) % len(COLOR_PALETTE)])
        self._classes.append(name)
        self._colors[name] = color
        return color

    def remove_class(self, name: str) -> None:
        if name in self._colors:
            self._classes.remove(name)
            del self._colors[name]

    def get_color(self, name: str) -> QColor:
        return self._colors.get(name, QColor("#cccccc"))

    def has_class(self, name: str) -> bool:
        return name in self._colors

    def set_classes(self, names: list[str]) -> None:
        """Replace entire class list."""
        self._classes.clear()
        self._colors.clear()
        for name in names:
            self.add_class(name)
