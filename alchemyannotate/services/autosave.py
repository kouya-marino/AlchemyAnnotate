from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QTimer, Signal

if TYPE_CHECKING:
    from alchemyannotate.services.annotation_store import AnnotationStore
    from alchemyannotate.services.io_router import IORouter


class AutosaveService(QObject):
    """Debounced autosave that writes dirty annotations to disk."""

    save_failed = Signal(str)  # error message

    def __init__(
        self,
        store: AnnotationStore,
        io_router: IORouter,
        class_list_getter,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._store = store
        self._io_router = io_router
        self._class_list_getter = class_list_getter
        self._enabled = True

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._do_save)

        self._store.annotation_changed.connect(self._on_change)

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value
        if not value:
            self._timer.stop()

    def _on_change(self, _filename: str) -> None:
        if self._enabled:
            self._timer.start()

    def save_now(self) -> None:
        """Force immediate save of all dirty files."""
        self._timer.stop()
        self._do_save()

    def _do_save(self) -> None:
        from alchemyannotate.utils.constants import AnnotationFormat

        dirty = self._store.dirty_files()
        if not dirty:
            return

        class_list = self._class_list_getter()

        try:
            if self._io_router.format == AnnotationFormat.COCO:
                # COCO needs to write all annotations at once
                all_anns = {}
                for fname in self._store.all_filenames():
                    ann = self._store.get(fname)
                    if ann and ann.boxes:
                        all_anns[fname] = ann
                self._io_router.save_all(all_anns, class_list)
                for fname in dirty:
                    self._store.mark_clean(fname)
            else:
                for fname in dirty:
                    ann = self._store.get(fname)
                    if ann:
                        self._io_router.save_annotation(ann, class_list)
                    self._store.mark_clean(fname)
        except Exception as e:
            self.save_failed.emit(str(e))
