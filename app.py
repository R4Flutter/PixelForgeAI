from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt, qVersion
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from backend.state import paths
from backend.updater import APP_NAME
from bootstrap import bootstrap
from gui.main_window import MainWindow
from gui.splash import SplashScreen


def _load_theme(app: QApplication, name: str = "dark") -> None:
    qss = paths().theme_file(name)
    try:
        app.setStyleSheet(qss.read_text(encoding="utf-8"))
    except OSError:
        pass


def main() -> int:
    ver = qVersion().split(".")
    if not (int(ver[0]) >= 6 and int(ver[1]) >= 6):
        if hasattr(Qt, "AA_EnableHighDpiScaling"):
            QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_NAME)
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    _load_theme(app, "dark")

    di = bootstrap()
    splash = SplashScreen()
    window = MainWindow(di)
    splash.entered.connect(lambda: splash.finish_and_close(window))
    splash.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
