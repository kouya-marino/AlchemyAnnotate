from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF
from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox, QProgressDialog

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
        mw.draw_mode_toggled.connect(self._on_draw_mode_toggled)
        mw.polygon_mode_toggled.connect(self._on_polygon_mode_toggled)
        mw.edit_class_requested.connect(self._on_edit_class_requested)

        # Undo/Redo/Copy/Paste
        mw.undo_requested.connect(self._on_undo)
        mw.redo_requested.connect(self._on_redo)
        mw.copy_requested.connect(self._canvas_ctrl.copy_selected)
        mw.paste_requested.connect(self._on_paste)

        # Labels toggle
        mw.labels_toggled.connect(self._on_labels_toggled)

        # Statistics
        mw.show_stats_requested.connect(self._on_show_stats)

        # Drag-and-drop
        mw.folder_dropped.connect(self._on_folder_dropped)

        # Sidebar
        mw.sidebar.image_selected.connect(self._on_sidebar_image_selected)

        # Navigation
        self._nav_ctrl.image_changed.connect(self._on_image_changed)

        # Canvas controller
        self._canvas_ctrl.box_created.connect(self._on_box_modified)
        self._canvas_ctrl.box_deleted.connect(self._on_box_modified)
        self._canvas_ctrl.box_modified.connect(self._on_box_modified)
        self._canvas_ctrl.selection_changed.connect(self._on_selection_changed)
        self._canvas_ctrl.class_prompt_needed.connect(self._on_class_prompt_needed)
        self._canvas_ctrl.polygon_class_prompt_needed.connect(self._on_polygon_class_prompt_needed)

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

    def _on_folder_dropped(self, folder_str: str) -> None:
        self._open_folder(Path(folder_str))

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
            load_fmt = None
            project_fmt = AnnotationFormat(self._project_config.annotation_format)
            if project_fmt in existing_formats:
                load_fmt = project_fmt
            else:
                load_fmt = existing_formats[0]

            self._io_router.format = load_fmt
            self.main_window.set_format(load_fmt.value)

            image_sizes = {}
            for fname in images:
                image_sizes[fname] = self._image_loader.get_image_size(fname)

            class_list = self._class_registry.classes

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

            for ann in all_anns.values():
                for box in ann.boxes:
                    if not self._class_registry.has_class(box.class_name):
                        self._class_registry.add_class(box.class_name)

    # -- Image navigation --

    def _on_sidebar_image_selected(self, filename: str) -> None:
        self._nav_ctrl.go_to_image(filename)

    def _on_image_changed(self, filename: str) -> None:
        pixmap = self._image_loader.load_pixmap(filename)
        if not pixmap:
            return

        self.main_window.canvas.set_image(pixmap)

        img_w, img_h = pixmap.width(), pixmap.height()
        ann = self._annotation_store.get_or_create(filename, img_w, img_h)
        if ann.image_width == 0:
            ann.image_width = img_w
            ann.image_height = img_h

        if not ann.boxes and self._io_router:
            loaded = self._io_router.load_annotation(
                filename, img_w, img_h, self._class_registry.classes
            )
            if loaded and loaded.boxes:
                ann.boxes = loaded.boxes
                ann.image_width = loaded.image_width or img_w
                ann.image_height = loaded.image_height or img_h
                self._annotation_store.mark_clean(filename)
                for box in loaded.boxes:
                    if not self._class_registry.has_class(box.class_name):
                        self._class_registry.add_class(box.class_name)
                self._refresh_class_panel()

        self._canvas_ctrl.set_current_image(filename)
        self._canvas_ctrl.render_boxes(filename)
        self._refresh_box_list()
        self._refresh_labels()

        self._project_config.last_opened_image = filename
        self._save_project_config()

    # -- Box operations --

    def _on_box_modified(self, _box_id: str) -> None:
        self._refresh_box_list()
        self._refresh_labels()
        self._update_current_sidebar_status()

    def _on_selection_changed(self, box_id: str) -> None:
        self.main_window.box_list_panel.select_box(box_id if box_id else None)

    def _on_box_highlight(self, box_id: str) -> None:
        self.main_window.canvas.highlight_box(box_id)

    def _on_box_delete_from_list(self, box_id: str) -> None:
        self._canvas_ctrl._selected_box_id = box_id
        self._canvas_ctrl.delete_selected()

    def _on_box_class_changed(self, box_id: str, new_class: str) -> None:
        self._canvas_ctrl.change_box_class(box_id, new_class)
        self._refresh_box_list()
        self._refresh_labels()

    # -- Undo/Redo --

    def _on_undo(self) -> None:
        self._canvas_ctrl.undo()

    def _on_redo(self) -> None:
        self._canvas_ctrl.redo()

    # -- Copy/Paste --

    def _on_paste(self) -> None:
        self._canvas_ctrl.paste()

    # -- Labels --

    def _on_labels_toggled(self, visible: bool) -> None:
        self.main_window.canvas.set_labels_visible(visible)
        if visible:
            self._refresh_labels()

    def _refresh_labels(self) -> None:
        filename = self._nav_ctrl.current_filename
        if not filename:
            return
        ann = self._annotation_store.get(filename)
        if not ann:
            return
        box_labels = {box.id: box.class_name for box in ann.boxes}
        self.main_window.canvas.update_labels(box_labels)

    # -- Statistics --

    def _on_show_stats(self) -> None:
        total_images = len(self._image_loader.image_list)
        labeled = 0
        total_annotations = 0
        bbox_count = 0
        polygon_count = 0
        class_counts: dict[str, int] = {}

        for fname in self._image_loader.image_list:
            ann = self._annotation_store.get(fname)
            if ann and ann.boxes:
                labeled += 1
                for box in ann.boxes:
                    total_annotations += 1
                    if box.annotation_type == "polygon":
                        polygon_count += 1
                    else:
                        bbox_count += 1
                    class_counts[box.class_name] = class_counts.get(box.class_name, 0) + 1

        lines = [
            f"<b>Images:</b> {labeled} labeled / {total_images} total",
            f"<b>Annotations:</b> {total_annotations} ({bbox_count} boxes, {polygon_count} polygons)",
            "",
            "<b>Per-class counts:</b>",
        ]
        if class_counts:
            for cls, cnt in sorted(class_counts.items(), key=lambda x: -x[1]):
                lines.append(f"&nbsp;&nbsp;{cls}: {cnt}")
        else:
            lines.append("&nbsp;&nbsp;(none)")

        QMessageBox.information(
            self.main_window,
            "Annotation Statistics",
            "<br>".join(lines),
        )

    # -- Class management --

    def _on_class_added(self, name: str) -> None:
        name = name.strip()
        if not name:
            self.main_window.show_status_message("Class name cannot be empty")
            return
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

    # -- Toolbar actions --

    def _on_draw_mode_toggled(self, enabled: bool) -> None:
        self.main_window.canvas.set_draw_enabled(enabled)
        if enabled:
            self._canvas_ctrl.set_annotation_mode("bbox")

    def _on_polygon_mode_toggled(self, enabled: bool) -> None:
        self.main_window.canvas.set_draw_enabled(enabled)
        if enabled:
            self._canvas_ctrl.set_annotation_mode("polygon")

    def _on_polygon_class_prompt_needed(self, points) -> None:
        from alchemyannotate.views.dialogs import ClassSelectDialog

        active = self._canvas_ctrl._active_class or self._project_config.recently_used_class
        dialog = ClassSelectDialog(self._class_registry.classes, active, self.main_window)
        if dialog.exec() != ClassSelectDialog.DialogCode.Accepted:
            return

        name = dialog.selected_class
        if dialog.is_new_class and not self._class_registry.has_class(name):
            self._class_registry.add_class(name)
            self._refresh_class_panel()
            self._update_project_classes()

        self._canvas_ctrl.set_active_class(name)
        self._project_config.recently_used_class = name
        self._canvas_ctrl.create_polygon(points, name)

    def _on_class_prompt_needed(self, rect) -> None:
        from PySide6.QtCore import QRectF
        from alchemyannotate.views.dialogs import ClassSelectDialog

        active = self._canvas_ctrl._active_class or self._project_config.recently_used_class
        dialog = ClassSelectDialog(self._class_registry.classes, active, self.main_window)
        if dialog.exec() != ClassSelectDialog.DialogCode.Accepted:
            return

        name = dialog.selected_class
        if not name.strip():
            self.main_window.show_status_message("Class name cannot be empty")
            return
        if dialog.is_new_class and not self._class_registry.has_class(name):
            self._class_registry.add_class(name)
            self._refresh_class_panel()
            self._update_project_classes()

        self._canvas_ctrl.set_active_class(name)
        self._project_config.recently_used_class = name
        self._canvas_ctrl.create_box(QRectF(rect), name)

    def _on_edit_class_requested(self) -> None:
        box_id = self._canvas_ctrl.selected_box_id
        if not box_id:
            self.main_window.show_status_message("No annotation selected")
            return

        classes = self._class_registry.classes
        if not classes:
            self.main_window.show_status_message("No classes defined")
            return

        current_class = ""
        filename = self._nav_ctrl.current_filename
        if filename:
            ann = self._annotation_store.get(filename)
            if ann:
                for box in ann.boxes:
                    if box.id == box_id:
                        current_class = box.class_name
                        break

        current_idx = classes.index(current_class) if current_class in classes else 0
        new_class, ok = QInputDialog.getItem(
            self.main_window,
            "Edit Class",
            "Select class for this annotation:",
            classes,
            current_idx,
            False,
        )
        if ok and new_class:
            self._canvas_ctrl.change_box_class(box_id, new_class)
            self._refresh_box_list()
            self._refresh_labels()

    # -- Format --

    def _on_format_changed(self, fmt_str: str) -> None:
        new_fmt = AnnotationFormat(fmt_str)
        if not self._io_router:
            return

        old_fmt = self._io_router.format
        if new_fmt == old_fmt:
            return

        # Warn about polygon data loss when switching to VOC
        if new_fmt == AnnotationFormat.VOC:
            has_polygons = False
            for fname in self._image_loader.image_list:
                ann = self._annotation_store.get(fname)
                if ann:
                    if any(b.annotation_type == "polygon" for b in ann.boxes):
                        has_polygons = True
                        break
            if has_polygons:
                reply = QMessageBox.warning(
                    self.main_window,
                    "Polygon Data Loss",
                    "Pascal VOC format does not support polygon annotations.\n"
                    "Polygon data will be lost during export.\n\n"
                    "Do you want to continue?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.No:
                    self.main_window.set_format(old_fmt.value)
                    return

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
