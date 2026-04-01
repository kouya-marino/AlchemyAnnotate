import sys

from PySide6.QtWidgets import QApplication


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("AlchemyAnnotate")

    from alchemyannotate.controllers.app_controller import AppController

    controller = AppController()
    controller.main_window.show()
    sys.exit(app.exec())
