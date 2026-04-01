from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QAction, QKeySequence, QIcon, QPixmap, QPainter, QColor, QPen
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
)

from alchemyannotate.views.canvas import AnnotationCanvas
from alchemyannotate.views.sidebar import ImageSidebar
from alchemyannotate.views.class_panel import ClassPanel
from alchemyannotate.views.box_list_panel import BoxListPanel
from alchemyannotate.utils.constants import AnnotationFormat


def _make_icon_draw() -> QIcon:
    """Create a draw-box icon (rectangle outline)."""
    pm = QPixmap(24, 24)
    pm.fill(QColor("transparent"))
    p = QPainter(pm)
    p.setPen(QPen(QColor("#4363d8"), 2))
    p.drawRect(4, 4, 16, 16)
    p.end()
    return QIcon(pm)


def _make_icon_delete() -> QIcon:
    """Create a delete icon (X mark)."""
    pm = QPixmap(24, 24)
    pm.fill(QColor("transparent"))
    p = QPainter(pm)
    p.setPen(QPen(QColor("#e6194b"), 2))
    p.drawLine(5, 5, 19, 19)
    p.drawLine(19, 5, 5, 19)
    p.end()
    return QIcon(pm)


def _make_icon_edit() -> QIcon:
    """Create an edit icon (pencil shape)."""
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


class MainWindow(QMainWindow):
    """Main application window."""

    # Menu/toolbar signals
    open_folder_requested = Signal()
    save_requested = Signal()
    export_all_requested = Signal()
    format_changed = Signal(str)  # new format string
    delete_box_requested = Signal()
    fit_to_window_requested = Signal()
    prev_image_requested = Signal()
    next_image_requested = Signal()
    draw_mode_toggled = Signal(bool)        # True = draw mode on
    edit_class_requested = Signal()          # edit class of selected box

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("AlchemyAnnotate")
        self.setMinimumSize(1000, 700)

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

        delete_action = QAction("&Delete Box", self)
        delete_action.setShortcut(QKeySequence("Delete"))
        delete_action.triggered.connect(self.delete_box_requested.emit)
        edit_menu.addAction(delete_action)

        # View menu
        view_menu = menubar.addMenu("&View")

        fit_action = QAction("&Fit to Window", self)
        fit_action.setShortcut(QKeySequence("Ctrl+0"))
        fit_action.triggered.connect(self.fit_to_window_requested.emit)
        view_menu.addAction(fit_action)

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

    def _setup_toolbar(self) -> None:
        toolbar = QToolBar("Annotation Tools")
        toolbar.setIconSize(QSize(24, 24))
        toolbar.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

        # Draw Box (toggle)
        self._draw_action = QAction(_make_icon_draw(), "Draw Box", self)
        self._draw_action.setCheckable(True)
        self._draw_action.setChecked(True)
        self._draw_action.setToolTip("Draw bounding box (left-click drag on image)")
        self._draw_action.setShortcut(QKeySequence("B"))
        self._draw_action.toggled.connect(self._on_draw_toggled)
        toolbar.addAction(self._draw_action)

        toolbar.addSeparator()

        # Delete Box
        self._delete_action = QAction(_make_icon_delete(), "Delete Box", self)
        self._delete_action.setToolTip("Delete selected box (Del)")
        self._delete_action.setShortcut(QKeySequence("Delete"))
        self._delete_action.triggered.connect(self.delete_box_requested.emit)
        toolbar.addAction(self._delete_action)

        toolbar.addSeparator()

        # Edit Class
        self._edit_class_action = QAction(_make_icon_edit(), "Edit Class", self)
        self._edit_class_action.setToolTip("Change class of selected box (E)")
        self._edit_class_action.setShortcut(QKeySequence("E"))
        self._edit_class_action.triggered.connect(self.edit_class_requested.emit)
        toolbar.addAction(self._edit_class_action)

    def _on_draw_toggled(self, checked: bool) -> None:
        self.draw_mode_toggled.emit(checked)

    def set_draw_mode(self, enabled: bool) -> None:
        """Update the draw action state without emitting signal."""
        self._draw_action.blockSignals(True)
        self._draw_action.setChecked(enabled)
        self._draw_action.blockSignals(False)

    def _setup_shortcuts(self) -> None:
        pass  # Shortcuts are set via menu actions and toolbar above

    def _on_format_changed(self, index: int) -> None:
        fmt = self._format_combo.itemData(index)
        if fmt:
            self.format_changed.emit(fmt)

    # -- Public update methods --

    def update_image_index(self, current: int, total: int) -> None:
        if total == 0:
            self._index_label.setText("No images loaded")
        else:
            self._index_label.setText(f"{current + 1} / {total}")

    def set_format(self, fmt: str) -> None:
        """Set the format combo without emitting signal."""
        self._format_combo.blockSignals(True)
        index = self._format_combo.findData(fmt)
        if index >= 0:
            self._format_combo.setCurrentIndex(index)
        self._format_combo.blockSignals(False)

    def show_status_message(self, msg: str, timeout: int = 3000) -> None:
        self._status_bar.showMessage(msg, timeout)
