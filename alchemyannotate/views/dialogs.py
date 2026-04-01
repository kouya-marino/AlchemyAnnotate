from __future__ import annotations

from enum import Enum

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QButtonGroup,
    QDialogButtonBox,
)


class FormatSwitchChoice(Enum):
    EXPORT_AND_SWITCH = "export_and_switch"
    START_NEW = "start_new"
    CANCEL = "cancel"


class AnnotationDetectedChoice(Enum):
    LOAD_EXISTING = "load_existing"
    CREATE_NEW = "create_new"
    CANCEL = "cancel"


class FormatSwitchDialog(QDialog):
    """Dialog shown when user switches annotation format and existing annotations exist."""

    def __init__(self, current_format: str, new_format: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Switch Annotation Format")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            f"Existing annotations are available in <b>{current_format.upper()}</b> format.\n"
            f"Do you want to export them to <b>{new_format.upper()}</b>?"
        ))

        self._group = QButtonGroup(self)
        self._radio_export = QRadioButton("Export existing annotations and switch")
        self._radio_export.setChecked(True)
        self._radio_new = QRadioButton("Start new annotations (keep existing)")
        self._radio_cancel = QRadioButton("Cancel")
        self._group.addButton(self._radio_export)
        self._group.addButton(self._radio_new)
        self._group.addButton(self._radio_cancel)

        layout.addWidget(self._radio_export)
        layout.addWidget(self._radio_new)
        layout.addWidget(self._radio_cancel)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

        self.choice = FormatSwitchChoice.CANCEL

    def accept(self) -> None:
        if self._radio_export.isChecked():
            self.choice = FormatSwitchChoice.EXPORT_AND_SWITCH
        elif self._radio_new.isChecked():
            self.choice = FormatSwitchChoice.START_NEW
        else:
            self.choice = FormatSwitchChoice.CANCEL
        super().accept()


class AnnotationDetectedDialog(QDialog):
    """Dialog shown when existing annotations are detected on folder open."""

    def __init__(self, detected_formats: list[str], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Existing Annotations Detected")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        fmt_str = ", ".join(f.upper() for f in detected_formats)
        layout.addWidget(QLabel(
            f"Existing annotations were found in: <b>{fmt_str}</b>\n\n"
            "What would you like to do?"
        ))

        self._group = QButtonGroup(self)
        self._radio_load = QRadioButton("Load existing annotations")
        self._radio_load.setChecked(True)
        self._radio_new = QRadioButton("Create new annotations (separate folder)")
        self._radio_cancel = QRadioButton("Cancel")
        self._group.addButton(self._radio_load)
        self._group.addButton(self._radio_new)
        self._group.addButton(self._radio_cancel)

        layout.addWidget(self._radio_load)
        layout.addWidget(self._radio_new)
        layout.addWidget(self._radio_cancel)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

        self.choice = AnnotationDetectedChoice.CANCEL

    def accept(self) -> None:
        if self._radio_load.isChecked():
            self.choice = AnnotationDetectedChoice.LOAD_EXISTING
        elif self._radio_new.isChecked():
            self.choice = AnnotationDetectedChoice.CREATE_NEW
        else:
            self.choice = AnnotationDetectedChoice.CANCEL
        super().accept()
