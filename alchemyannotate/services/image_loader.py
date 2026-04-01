from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtGui import QImageReader, QPixmap

from alchemyannotate.utils.constants import IMAGE_EXTENSIONS


class ImageLoader:
    """Scans a folder for images and provides cached QPixmap loading."""

    def __init__(self, cache_size: int = 5) -> None:
        self._folder: Path | None = None
        self._image_list: list[str] = []
        self._cache: OrderedDict[str, QPixmap] = OrderedDict()
        self._cache_size = cache_size

    @property
    def folder(self) -> Path | None:
        return self._folder

    @property
    def image_list(self) -> list[str]:
        return self._image_list

    def scan_folder(self, folder: str | Path) -> list[str]:
        """Scan folder for image files, return sorted filename list."""
        self._folder = Path(folder)
        self._image_list = sorted(
            f.name
            for f in self._folder.iterdir()
            if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
        )
        self._cache.clear()
        return self._image_list

    def load_pixmap(self, filename: str) -> QPixmap | None:
        """Load a QPixmap for the given filename, with LRU caching."""
        if not self._folder:
            return None

        if filename in self._cache:
            self._cache.move_to_end(filename)
            return self._cache[filename]

        path = self._folder / filename
        if not path.exists():
            return None

        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return None

        self._cache[filename] = pixmap
        while len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)

        return pixmap

    def get_image_size(self, filename: str) -> tuple[int, int]:
        """Return (width, height) without loading full pixmap."""
        if not self._folder:
            return 0, 0
        path = self._folder / filename
        reader = QImageReader(str(path))
        size: QSize = reader.size()
        if size.isValid():
            return size.width(), size.height()
        # Fallback: load pixmap
        pm = self.load_pixmap(filename)
        if pm:
            return pm.width(), pm.height()
        return 0, 0
