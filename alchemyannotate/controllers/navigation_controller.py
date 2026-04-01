from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

if TYPE_CHECKING:
    from alchemyannotate.services.image_loader import ImageLoader
    from alchemyannotate.views.main_window import MainWindow


class NavigationController(QObject):
    """Tracks current image index and handles navigation."""

    image_changed = Signal(str)  # emits new filename

    def __init__(
        self,
        image_loader: ImageLoader,
        main_window: MainWindow,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._loader = image_loader
        self._window = main_window
        self._current_index: int = -1

    @property
    def current_index(self) -> int:
        return self._current_index

    @property
    def current_filename(self) -> str | None:
        images = self._loader.image_list
        if 0 <= self._current_index < len(images):
            return images[self._current_index]
        return None

    @property
    def total_images(self) -> int:
        return len(self._loader.image_list)

    def go_to_image(self, filename_or_index) -> None:
        """Navigate to an image by filename or index."""
        images = self._loader.image_list
        if not images:
            return

        if isinstance(filename_or_index, int):
            index = max(0, min(filename_or_index, len(images) - 1))
        else:
            try:
                index = images.index(filename_or_index)
            except ValueError:
                return

        if index == self._current_index:
            return

        self._current_index = index
        filename = images[index]
        self._update_status()
        self._window.sidebar.select_image(filename)
        self.image_changed.emit(filename)

    def go_prev(self) -> None:
        if self._current_index > 0:
            self.go_to_image(self._current_index - 1)

    def go_next(self) -> None:
        if self._current_index < len(self._loader.image_list) - 1:
            self.go_to_image(self._current_index + 1)

    def go_first(self) -> None:
        if self._loader.image_list:
            self.go_to_image(0)

    def _update_status(self) -> None:
        self._window.update_image_index(self._current_index, len(self._loader.image_list))
