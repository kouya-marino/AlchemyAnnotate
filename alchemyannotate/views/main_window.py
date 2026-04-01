from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QSize, QMimeData
from PySide6.QtGui import (
    QAction, QActionGroup, QKeySequence, QIcon, QPixmap, QPainter,
    QColor, QPen, QPalette, QDragEnterEvent, QDropEvent,
)
from PySide6.QtWidgets import (
    QMainWindow,
    QDockWidget,
    QSplitter,
    QWidget,
    QVBoxLayout,
    QLabel,
    QComboBox,
    QStatusBar,
    QMenuBar,
    QToolBar,
    QInputDialog,
    QApplication,
)

from alchemyannotate.views.canvas import AnnotationCanvas
from alchemyannotate.views.sidebar import ImageSidebar
from alchemyannotate.views.class_panel import ClassPanel
from alchemyannotate.views.box_list_panel import BoxListPanel
from alchemyannotate.utils.constants import AnnotationFormat


def _make_icon_draw() -> QIcon:
    pm = QPixmap(24, 24)
    pm.fill(QColor("transparent"))
    p = QPainter(pm)
    p.setPen(QPen(QColor("#4363d8"), 2))
    p.drawRect(4, 4, 16, 16)
    p.end()
    return QIcon(pm)


def _make_icon_delete() -> QIcon:
    pm = QPixmap(24, 24)
    pm.fill(QColor("transparent"))
    p = QPainter(pm)
    p.setPen(QPen(QColor("#e6194b"), 2))
    p.drawLine(5, 5, 19, 19)
    p.drawLine(19, 5, 5, 19)
    p.end()
    return QIcon(pm)


def _make_icon_edit() -> QIcon:
    pm = QPixmap(24, 24)
    pm.fill(QColor("transparent"))
    p = QPainter(pm)
    p.setPen(QPen(QColor("#3cb44b"), 2))
    p.drawLine(4, 20, 18, 6)
    p.drawLine(18, 6, 20, 4)
    p.drawLine(4, 20, 6, 18)
    p.drawLine(4, 20, 2, 22)
    p.end()
    return QIcon(pm)


def _make_icon_polygon() -> QIcon:
    pm = QPixmap(24, 24)
    pm.fill(QColor("transparent"))
    p = QPainter(pm)
    p.setPen(QPen(QColor("#f58231"), 2))
    p.drawLine(12, 3, 3, 20)
    p.drawLine(3, 20, 21, 20)
    p.drawLine(21, 20, 12, 3)
    p.end()
    return QIcon(pm)


class MainWindow(QMainWindow):
    """Main application window."""

    # Menu/toolbar signals
    open_folder_requested = Signal()
    save_requested = Signal()
    export_all_requested = Signal()
    format_changed = Signal(str)
    delete_box_requested = Signal()
    fit_to_window_requested = Signal()
    prev_image_requested = Signal()
    next_image_requested = Signal()
    draw_mode_toggled = Signal(bool)
    polygon_mode_toggled = Signal(bool)
    edit_class_requested = Signal()
    undo_requested = Signal()
    redo_requested = Signal()
    copy_requested = Signal()
    paste_requested = Signal()
    labels_toggled = Signal(bool)
    show_stats_requested = Signal()
    folder_dropped = Signal(str)           # folder path from drag-drop

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("AlchemyAnnotate")
        self.setMinimumSize(1000, 700)

        # Accept drag-and-drop
        self.setAcceptDrops(True)

        # Central canvas
        self.canvas = AnnotationCanvas()
        self.setCentralWidget(self.canvas)

        # Left dock: image sidebar
        self.sidebar = ImageSidebar()
        left_dock = QDockWidget("Images", self)
        left_dock.setWidget(self.sidebar)
        left_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, left_dock)

        # Right dock: class panel + box list
        self.class_panel = ClassPanel()
        self.box_list_panel = BoxListPanel()
        right_splitter = QSplitter(Qt.Orientation.Vertical)
        right_splitter.addWidget(self.class_panel)
        right_splitter.addWidget(self.box_list_panel)
        right_splitter.setStretchFactor(0, 1)
        right_splitter.setStretchFactor(1, 2)

        right_dock = QDockWidget("Annotation", self)
        right_dock.setWidget(right_splitter)
        right_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, right_dock)

        # Status bar
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)

        self._index_label = QLabel("No images loaded")
        self._status_bar.addWidget(self._index_label)

        self._zoom_label = QLabel("100%")
        self._status_bar.addPermanentWidget(self._zoom_label)

        self._format_label = QLabel()
        self._status_bar.addPermanentWidget(self._format_label)

        self._autosave_label = QLabel()
        self._status_bar.addPermanentWidget(self._autosave_label)

        # Format combo in status bar
        self._format_combo = QComboBox()
        for fmt in AnnotationFormat:
            self._format_combo.addItem(fmt.value.upper(), fmt.value)
        self._format_combo.currentIndexChanged.connect(self._on_format_changed)
        self._status_bar.addPermanentWidget(QLabel("Format:"))
        self._status_bar.addPermanentWidget(self._format_combo)

        # Connect zoom signal
        self.canvas.zoom_changed.connect(self._on_zoom_changed)

        # Dark theme state
        self._dark_theme = False

        self._setup_menus()
        self._setup_toolbar()
        self._setup_shortcuts()

    def _setup_menus(self) -> None:
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        open_action = QAction("&Open Folder...", self)
        open_action.setShortcut(QKeySequence("Ctrl+O"))
        open_action.triggered.connect(self.open_folder_requested.emit)
        file_menu.addAction(open_action)

        save_action = QAction("&Save", self)
        save_action.setShortcut(QKeySequence("Ctrl+S"))
        save_action.triggered.connect(self.save_requested.emit)
        file_menu.addAction(save_action)

        export_action = QAction("&Export All...", self)
        export_action.triggered.connect(self.export_all_requested.emit)
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        quit_action = QAction("&Quit", self)
        quit_action.setShortcut(QKeySequence("Ctrl+Q"))
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # Edit menu
        edit_menu = menubar.addMenu("&Edit")

        self._undo_action = QAction("&Undo", self)
        self._undo_action.setShortcut(QKeySequence("Ctrl+Z"))
        self._undo_action.triggered.connect(self.undo_requested.emit)
        edit_menu.addAction(self._undo_action)

        self._redo_action = QAction("&Redo", self)
        self._redo_action.setShortcut(QKeySequence("Ctrl+Shift+Z"))
        self._redo_action.triggered.connect(self.redo_requested.emit)
        edit_menu.addAction(self._redo_action)

        edit_menu.addSeparator()

        copy_action = QAction("&Copy Annotation", self)
        copy_action.setShortcut(QKeySequence("Ctrl+C"))
        copy_action.triggered.connect(self.copy_requested.emit)
        edit_menu.addAction(copy_action)

        paste_action = QAction("&Paste Annotation", self)
        paste_action.setShortcut(QKeySequence("Ctrl+V"))
        paste_action.triggered.connect(self.paste_requested.emit)
        edit_menu.addAction(paste_action)

        edit_menu.addSeparator()

        delete_action = QAction("&Delete Annotation", self)
        delete_action.setShortcut(QKeySequence("Delete"))
        delete_action.triggered.connect(self.delete_box_requested.emit)
        edit_menu.addAction(delete_action)

        # View menu
        view_menu = menubar.addMenu("&View")

        fit_action = QAction("&Fit to Window", self)
        fit_action.setShortcut(QKeySequence("Ctrl+0"))
        fit_action.triggered.connect(self.fit_to_window_requested.emit)
        view_menu.addAction(fit_action)

        self._labels_action = QAction("Show &Labels", self)
        self._labels_action.setCheckable(True)
        self._labels_action.setShortcut(QKeySequence("L"))
        self._labels_action.toggled.connect(self.labels_toggled.emit)
        view_menu.addAction(self._labels_action)

        view_menu.addSeparator()

        self._dark_action = QAction("&Dark Theme", self)
        self._dark_action.setCheckable(True)
        self._dark_action.toggled.connect(self._toggle_dark_theme)
        view_menu.addAction(self._dark_action)

        view_menu.addSeparator()

        stats_action = QAction("Annotation &Statistics...", self)
        stats_action.triggered.connect(self.show_stats_requested.emit)
        view_menu.addAction(stats_action)

        # Navigate menu
        nav_menu = menubar.addMenu("&Navigate")

        prev_action = QAction("&Previous Image", self)
        prev_action.setShortcuts([QKeySequence("A"), QKeySequence(Qt.Key.Key_Left)])
        prev_action.triggered.connect(self.prev_image_requested.emit)
        nav_menu.addAction(prev_action)

        next_action = QAction("&Next Image", self)
        next_action.setShortcuts([QKeySequence("D"), QKeySequence(Qt.Key.Key_Right)])
        next_action.triggered.connect(self.next_image_requested.emit)
        nav_menu.addAction(next_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")
        shortcuts_action = QAction("&Keyboard Shortcuts", self)
        shortcuts_action.setShortcut(QKeySequence("F1"))
        shortcuts_action.triggered.connect(self._show_shortcuts_dialog)
        help_menu.addAction(shortcuts_action)

    def _setup_toolbar(self) -> None:
        toolbar = QToolBar("Annotation Tools")
        toolbar.setIconSize(QSize(24, 24))
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        toolbar.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

        # Draw mode action group — mutually exclusive
        self._draw_group = QActionGroup(self)
        self._draw_group.setExclusive(False)

        # Draw Box (toggle)
        self._draw_action = QAction(_make_icon_draw(), "Draw Box", self)
        self._draw_action.setCheckable(True)
        self._draw_action.setChecked(True)
        self._draw_action.setToolTip("Draw bounding box [B]")
        self._draw_action.setShortcut(QKeySequence("B"))
        self._draw_action.toggled.connect(self._on_draw_toggled)
        self._draw_group.addAction(self._draw_action)
        toolbar.addAction(self._draw_action)

        # Draw Polygon (toggle)
        self._polygon_action = QAction(_make_icon_polygon(), "Draw Polygon", self)
        self._polygon_action.setCheckable(True)
        self._polygon_action.setToolTip("Draw polygon (click vertices, double-click to close) [P]")
        self._polygon_action.setShortcut(QKeySequence("P"))
        self._polygon_action.toggled.connect(self._on_polygon_toggled)
        self._draw_group.addAction(self._polygon_action)
        toolbar.addAction(self._polygon_action)

        toolbar.addSeparator()

        # Delete Box
        self._delete_action = QAction(_make_icon_delete(), "Delete", self)
        self._delete_action.setToolTip("Delete selected annotation [Del]")
        self._delete_action.triggered.connect(self.delete_box_requested.emit)
        toolbar.addAction(self._delete_action)

        toolbar.addSeparator()

        # Edit Class
        self._edit_class_action = QAction(_make_icon_edit(), "Edit Class", self)
        self._edit_class_action.setToolTip("Change class of selected annotation [E]")
        self._edit_class_action.setShortcut(QKeySequence("E"))
        self._edit_class_action.triggered.connect(self.edit_class_requested.emit)
        toolbar.addAction(self._edit_class_action)

    def _on_draw_toggled(self, checked: bool) -> None:
        if checked:
            self._polygon_action.blockSignals(True)
            self._polygon_action.setChecked(False)
            self._polygon_action.blockSignals(False)
        self.draw_mode_toggled.emit(checked)

    def _on_polygon_toggled(self, checked: bool) -> None:
        if checked:
            self._draw_action.blockSignals(True)
            self._draw_action.setChecked(False)
            self._draw_action.blockSignals(False)
            self.draw_mode_toggled.emit(False)
        self.polygon_mode_toggled.emit(checked)

    def set_draw_mode(self, enabled: bool) -> None:
        self._draw_action.blockSignals(True)
        self._draw_action.setChecked(enabled)
        self._draw_action.blockSignals(False)

    def _setup_shortcuts(self) -> None:
        pass  # Shortcuts are set via menu actions and toolbar above

    def _on_format_changed(self, index: int) -> None:
        fmt = self._format_combo.itemData(index)
        if fmt:
            self.format_changed.emit(fmt)

    def _on_zoom_changed(self, zoom_pct: float) -> None:
        self._zoom_label.setText(f"{zoom_pct:.0f}%")

    # -- Dark theme --

    def _toggle_dark_theme(self, enabled: bool) -> None:
        self._dark_theme = enabled
        app = QApplication.instance()
        if enabled:
            palette = QPalette()
            dark = QColor(45, 45, 45)
            mid = QColor(60, 60, 60)
            text = QColor(220, 220, 220)
            highlight = QColor(42, 130, 218)
            palette.setColor(QPalette.ColorRole.Window, dark)
            palette.setColor(QPalette.ColorRole.WindowText, text)
            palette.setColor(QPalette.ColorRole.Base, QColor(35, 35, 35))
            palette.setColor(QPalette.ColorRole.AlternateBase, mid)
            palette.setColor(QPalette.ColorRole.ToolTipBase, dark)
            palette.setColor(QPalette.ColorRole.ToolTipText, text)
            palette.setColor(QPalette.ColorRole.Text, text)
            palette.setColor(QPalette.ColorRole.Button, mid)
            palette.setColor(QPalette.ColorRole.ButtonText, text)
            palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
            palette.setColor(QPalette.ColorRole.Link, highlight)
            palette.setColor(QPalette.ColorRole.Highlight, highlight)
            palette.setColor(QPalette.ColorRole.HighlightedText, QColor(0, 0, 0))
            app.setPalette(palette)
        else:
            app.setPalette(app.style().standardPalette())

    # -- Drag and drop --

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        urls = event.mimeData().urls()
        if urls:
            from pathlib import Path
            path = Path(urls[0].toLocalFile())
            if path.is_dir():
                self.folder_dropped.emit(str(path))
            elif path.is_file():
                # If file dropped, use its parent folder
                self.folder_dropped.emit(str(path.parent))

    # -- Shortcuts help dialog --

    def _show_shortcuts_dialog(self) -> None:
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextBrowser, QDialogButtonBox
        dlg = QDialog(self)
        dlg.setWindowTitle("Keyboard Shortcuts")
        dlg.setMinimumSize(450, 500)
        layout = QVBoxLayout(dlg)
        browser = QTextBrowser()
        browser.setHtml("""
        <style>table { border-collapse: collapse; width: 100%; }
        th, td { text-align: left; padding: 4px 8px; border-bottom: 1px solid #555; }
        th { font-weight: bold; }</style>
        <h3>Drawing</h3>
        <table>
        <tr><td><b>B</b></td><td>Toggle Draw Box mode</td></tr>
        <tr><td><b>P</b></td><td>Toggle Draw Polygon mode</td></tr>
        <tr><td><b>Double-click</b></td><td>Close polygon</td></tr>
        <tr><td><b>Right-click / Esc</b></td><td>Cancel polygon drawing</td></tr>
        </table>
        <h3>Editing</h3>
        <table>
        <tr><td><b>Delete</b></td><td>Delete selected annotation</td></tr>
        <tr><td><b>E</b></td><td>Edit class of selected annotation</td></tr>
        <tr><td><b>Ctrl+Z</b></td><td>Undo</td></tr>
        <tr><td><b>Ctrl+Shift+Z</b></td><td>Redo</td></tr>
        <tr><td><b>Ctrl+C</b></td><td>Copy annotation</td></tr>
        <tr><td><b>Ctrl+V</b></td><td>Paste annotation</td></tr>
        </table>
        <h3>Navigation</h3>
        <table>
        <tr><td><b>A / Left</b></td><td>Previous image</td></tr>
        <tr><td><b>D / Right</b></td><td>Next image</td></tr>
        </table>
        <h3>View</h3>
        <table>
        <tr><td><b>Ctrl+0</b></td><td>Fit image to window</td></tr>
        <tr><td><b>Ctrl+Scroll</b></td><td>Zoom in/out</td></tr>
        <tr><td><b>Middle-click drag</b></td><td>Pan</td></tr>
        <tr><td><b>L</b></td><td>Toggle annotation labels</td></tr>
        </table>
        <h3>File</h3>
        <table>
        <tr><td><b>Ctrl+O</b></td><td>Open folder</td></tr>
        <tr><td><b>Ctrl+S</b></td><td>Save</td></tr>
        <tr><td><b>Ctrl+Q</b></td><td>Quit</td></tr>
        <tr><td><b>F1</b></td><td>Show this help</td></tr>
        </table>
        <h3>Tips</h3>
        <ul>
        <li>Drag and drop a folder onto the window to open it</li>
        <li>Right-click an annotation for context menu (Edit/Copy/Delete)</li>
        <li>Click a selected box to drag-move it</li>
        <li>Drag corner/edge handles to resize a box</li>
        <li>Drag polygon vertex handles to reshape</li>
        </ul>
        """)
        browser.setOpenExternalLinks(False)
        layout.addWidget(browser)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        btns.accepted.connect(dlg.accept)
        layout.addWidget(btns)
        dlg.exec()

    # -- Public update methods --

    def update_image_index(self, current: int, total: int) -> None:
        if total == 0:
            self._index_label.setText("No images loaded")
        else:
            self._index_label.setText(f"{current + 1} / {total}")

    def set_format(self, fmt: str) -> None:
        self._format_combo.blockSignals(True)
        index = self._format_combo.findData(fmt)
        if index >= 0:
            self._format_combo.setCurrentIndex(index)
        self._format_combo.blockSignals(False)

    def show_status_message(self, msg: str, timeout: int = 3000) -> None:
        self._status_bar.showMessage(msg, timeout)
