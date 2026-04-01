from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF
from PySide6.QtWidgets import QFileDialog

from alchemyannotate.controllers.canvas_controller import CanvasController
from alchemyannotate.controllers.navigation_controller import NavigationController
from alchemyannotate.models.class_registry import ClassRegistry
from alchemyannotate.models.project import ProjectConfig, PROJECT_FILENAME
from alchemyannotate.services.annotation_store import AnnotationStore
from alchemyannotate.services.autosave import AutosaveService
from alchemyannotate.services.format_converter import FormatConverter
from alchemyannotate.services.image_loader import ImageLoader
from alchemyannotate.services.io_router import IORouter
from alchemyannotate.utils.constants import AnnotationFormat
from alchemyannotate.views.dialogs import (
    AnnotationDetectedChoice,
    AnnotationDetectedDialog,
    FormatSwitchChoice,
    FormatSwitchDialog,
)
from alchemyannotate.views.main_window import MainWindow


class AppController:
    """Central orchestrator that wires all components together."""

    def __init__(self) -> None:
        # Models
        self._class_registry = ClassRegistry()
        self._project_config = ProjectConfig()

        # Services
        self._image_loader = ImageLoader()
        self._annotation_store = AnnotationStore()
        self._io_router: IORouter | None = None
        self._autosave: AutosaveService | None = None

        # Views
        self.main_window = MainWindow()

        # Controllers
        self._canvas_ctrl = CanvasController(
            self.main_window.canvas,
            self._annotation_store,
            self._class_registry,
        )
        self._nav_ctrl = NavigationController(
            self._image_loader,
            self.main_window,
        )

        self._connect_signals()

    def _connect_signals(self) -> None:
        mw = self.main_window

        # Menu/toolbar
        mw.open_folder_requested.connect(self._on_open_folder)
        mw.save_requested.connect(self._on_save)
        mw.export_all_requested.connect(self._on_export_all)
        mw.format_changed.connect(self._on_format_changed)
        mw.delete_box_requested.connect(self._canvas_ctrl.delete_selected)
        mw.fit_to_window_requested.connect(mw.canvas.fit_to_window)
        mw.prev_image_requested.connect(self._nav_ctrl.go_prev)
        mw.next_image_requested.connect(self._nav_ctrl.go_next)

        # Sidebar
        mw.sidebar.image_selected.connect(self._on_sidebar_image_selected)

        # Navigation
        self._nav_ctrl.image_changed.connect(self._on_image_changed)

        # Canvas controller
        self._canvas_ctrl.box_created.connect(self._on_box_modified)
        self._canvas_ctrl.box_deleted.connect(self._on_box_modified)
        self._canvas_ctrl.selection_changed.connect(self._on_selection_changed)

        # Class panel
        mw.class_panel.class_added.connect(self._on_class_added)
        mw.class_panel.class_deleted.connect(self._on_class_deleted)
        mw.class_panel.active_class_changed.connect(self._on_active_class_changed)

        # Box list panel
        mw.box_list_panel.box_highlight_requested.connect(self._on_box_highlight)
        mw.box_list_panel.box_delete_requested.connect(self._on_box_delete_from_list)
        mw.box_list_panel.box_class_changed.connect(self._on_box_class_changed)

    # -- Folder open --

    def _on_open_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self.main_window, "Select Image Folder"
        )
        if not folder:
            return
        self._open_folder(Path(folder))

    def _open_folder(self, folder: Path) -> None:
        # Load project config if it exists
        project_path = folder / PROJECT_FILENAME
        self._project_config = ProjectConfig.load(project_path)
        self._project_config.image_folder = str(folder)

        # Set format
        fmt = AnnotationFormat(self._project_config.annotation_format)
        self.main_window.set_format(fmt.value)

        # Set up IO router
        self._io_router = IORouter(folder, fmt)

        # Set up autosave
        if self._autosave:
            self._autosave.enabled = False
        self._autosave = AutosaveService(
            self._annotation_store,
            self._io_router,
            lambda: self._class_registry.classes,
        )
        self._autosave.save_failed.connect(
            lambda msg: self.main_window.show_status_message(f"Autosave failed: {msg}")
        )

        # Load classes
        self._class_registry.set_classes(self._project_config.class_list)

        # Scan images
        images = self._image_loader.scan_folder(folder)
        if not images:
            self.main_window.show_status_message("No images found in folder")
            return

        # Clear old state
        self._annotation_store.clear()

        # Detect existing annotations
        existing_formats = IORouter.detect_existing_formats(folder)
        if existing_formats:
            self._handle_existing_annotations(existing_formats, folder, images)

        # Update UI
        self.main_window.sidebar.set_images(images)
        self._refresh_class_panel()
        self._update_sidebar_statuses()

        # Navigate to last opened or first image
        start_image = self._project_config.last_opened_image
        if start_image and start_image in images:
            self._nav_ctrl.go_to_image(start_image)
        else:
            self._nav_ctrl.go_first()

        # Set recently used class as active
        if self._project_config.recently_used_class and self._class_registry.has_class(
            self._project_config.recently_used_class
        ):
            self._canvas_ctrl.set_active_class(self._project_config.recently_used_class)

    def _handle_existing_annotations(
        self, existing_formats: list[AnnotationFormat], folder: Path, images: list[str]
    ) -> None:
        dialog = AnnotationDetectedDialog(
            [f.value for f in existing_formats], self.main_window
        )
        dialog.exec()

        if dialog.choice == AnnotationDetectedChoice.CANCEL:
            return

        if dialog.choice == AnnotationDetectedChoice.LOAD_EXISTING:
            # Use the first detected format, or the project config format if available
            load_fmt = None
            project_fmt = AnnotationFormat(self._project_config.annotation_format)
            if project_fmt in existing_formats:
                load_fmt = project_fmt
            else:
                load_fmt = existing_formats[0]

            self._io_router.format = load_fmt
            self.main_window.set_format(load_fmt.value)

            # Get image sizes for YOLO loading
            image_sizes = {}
            for fname in images:
                image_sizes[fname] = self._image_loader.get_image_size(fname)

            class_list = self._class_registry.classes

            # Try to load classes.txt for YOLO
            if load_fmt == AnnotationFormat.YOLO:
                from alchemyannotate.services.io_yolo import YoloIO
                yolo_folder = folder / "annotations_yolo"
                yolo_classes = YoloIO.read_classes_txt(yolo_folder)
                if yolo_classes:
                    class_list = yolo_classes
                    self._class_registry.set_classes(class_list)

            all_anns = self._io_router.load_all(images, image_sizes, class_list)
            for fname, ann in all_anns.items():
                self._annotation_store.set(fname, ann)
                self._annotation_store.mark_clean(fname)

            # Update class registry with any new classes found
            for ann in all_anns.values():
                for box in ann.boxes:
                    if not self._class_registry.has_class(box.class_name):
                        self._class_registry.add_class(box.class_name)

    # -- Image navigation --

    def _on_sidebar_image_selected(self, filename: str) -> None:
        self._nav_ctrl.go_to_image(filename)

    def _on_image_changed(self, filename: str) -> None:
        # Load pixmap
        pixmap = self._image_loader.load_pixmap(filename)
        if not pixmap:
            return

        # Set up canvas
        self.main_window.canvas.set_image(pixmap)

        # Ensure annotation exists with correct dimensions
        img_w, img_h = pixmap.width(), pixmap.height()
        ann = self._annotation_store.get_or_create(filename, img_w, img_h)
        if ann.image_width == 0:
            ann.image_width = img_w
            ann.image_height = img_h

        # If no annotations in store, try loading from disk
        if not ann.boxes and self._io_router:
            loaded = self._io_router.load_annotation(
                filename, img_w, img_h, self._class_registry.classes
            )
            if loaded and loaded.boxes:
                ann.boxes = loaded.boxes
                ann.image_width = loaded.image_width or img_w
                ann.image_height = loaded.image_height or img_h
                self._annotation_store.mark_clean(filename)
                # Update class registry
                for box in loaded.boxes:
                    if not self._class_registry.has_class(box.class_name):
                        self._class_registry.add_class(box.class_name)
                self._refresh_class_panel()

        # Tell canvas controller about current image
        self._canvas_ctrl.set_current_image(filename)
        self._canvas_ctrl.render_boxes(filename)

        # Update box list
        self._refresh_box_list()

        # Update project config
        self._project_config.last_opened_image = filename
        self._save_project_config()

    # -- Box operations --

    def _on_box_modified(self, _box_id: str) -> None:
        self._refresh_box_list()
        self._update_current_sidebar_status()

    def _on_selection_changed(self, box_id: str) -> None:
        self.main_window.box_list_panel.select_box(box_id if box_id else None)

    def _on_box_highlight(self, box_id: str) -> None:
        self.main_window.canvas.highlight_box(box_id)

    def _on_box_delete_from_list(self, box_id: str) -> None:
        # Temporarily select the box, then delete
        self._canvas_ctrl._selected_box_id = box_id
        self._canvas_ctrl.delete_selected()

    def _on_box_class_changed(self, box_id: str, new_class: str) -> None:
        self._canvas_ctrl.change_box_class(box_id, new_class)
        self._refresh_box_list()

    # -- Class management --

    def _on_class_added(self, name: str) -> None:
        if self._class_registry.has_class(name):
            self.main_window.show_status_message(f"Class '{name}' already exists")
            return
        self._class_registry.add_class(name)
        self._refresh_class_panel()
        self._update_project_classes()

    def _on_class_deleted(self, name: str) -> None:
        self._class_registry.remove_class(name)
        self._refresh_class_panel()
        self._update_project_classes()

    def _on_active_class_changed(self, name: str) -> None:
        self._canvas_ctrl.set_active_class(name)
        self._project_config.recently_used_class = name

    # -- Format --

    def _on_format_changed(self, fmt_str: str) -> None:
        new_fmt = AnnotationFormat(fmt_str)
        if not self._io_router:
            return

        old_fmt = self._io_router.format
        if new_fmt == old_fmt:
            return

        # Check if there are existing annotations in the old format
        has_annotations = any(
            self._annotation_store.has_annotations(f)
            for f in self._image_loader.image_list
        )

        if has_annotations:
            dialog = FormatSwitchDialog(old_fmt.value, new_fmt.value, self.main_window)
            dialog.exec()

            if dialog.choice == FormatSwitchChoice.CANCEL:
                self.main_window.set_format(old_fmt.value)
                return
            elif dialog.choice == FormatSwitchChoice.EXPORT_AND_SWITCH:
                # Get image sizes
                image_sizes = {}
                for fname in self._image_loader.image_list:
                    image_sizes[fname] = self._image_loader.get_image_size(fname)

                FormatConverter.convert(
                    self._io_router._base_folder,
                    old_fmt,
                    new_fmt,
                    self._image_loader.image_list,
                    image_sizes,
                    self._class_registry.classes,
                )
                self.main_window.show_status_message(
                    f"Annotations exported from {old_fmt.value.upper()} to {new_fmt.value.upper()}"
                )

        self._io_router.format = new_fmt
        self._project_config.annotation_format = new_fmt.value
        self._save_project_config()

    # -- Save --

    def _on_save(self) -> None:
        if self._autosave:
            self._autosave.save_now()
            self.main_window.show_status_message("Saved")

    def _on_export_all(self) -> None:
        if not self._io_router:
            return
        all_anns = {}
        for fname in self._image_loader.image_list:
            ann = self._annotation_store.get(fname)
            if ann and ann.boxes:
                all_anns[fname] = ann
        if all_anns:
            self._io_router.save_all(all_anns, self._class_registry.classes)
            self.main_window.show_status_message(
                f"Exported {len(all_anns)} annotations in {self._io_router.format.value.upper()} format"
            )
        else:
            self.main_window.show_status_message("No annotations to export")

    # -- Helpers --

    def _refresh_class_panel(self) -> None:
        classes = [
            (name, self._class_registry.get_color(name))
            for name in self._class_registry.classes
        ]
        self.main_window.class_panel.set_classes(classes)
        self.main_window.box_list_panel.set_classes(self._class_registry.classes)

    def _refresh_box_list(self) -> None:
        filename = self._nav_ctrl.current_filename
        if not filename:
            self.main_window.box_list_panel.set_boxes([])
            return
        ann = self._annotation_store.get(filename)
        if not ann:
            self.main_window.box_list_panel.set_boxes([])
            return
        boxes = [b.to_dict() for b in ann.boxes]
        self.main_window.box_list_panel.set_boxes(boxes)

    def _update_sidebar_statuses(self) -> None:
        for fname in self._image_loader.image_list:
            has = self._annotation_store.has_annotations(fname)
            self.main_window.sidebar.update_status(fname, has)

    def _update_current_sidebar_status(self) -> None:
        filename = self._nav_ctrl.current_filename
        if filename:
            has = self._annotation_store.has_annotations(filename)
            self.main_window.sidebar.update_status(filename, has)

    def _update_project_classes(self) -> None:
        self._project_config.class_list = self._class_registry.classes
        self._save_project_config()

    def _save_project_config(self) -> None:
        folder = self._image_loader.folder
        if folder:
            self._project_config.save(folder / PROJECT_FILENAME)
