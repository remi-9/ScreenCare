"""Qt application bootstrap.

Phase 1 responsibility only: construct the Qt GUI application, load the root
QML window, and hand control to the Qt event loop. Business logic (the
focus/break/hydration engines, the ``WellnessCoordinator``, persistence, and
platform adapters) does not exist yet and must never be added here — see
``ARCHITECTURE.md``. This module's job is wiring, not behavior.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

logger = logging.getLogger(__name__)

QML_DIR = Path(__file__).resolve().parent.parent / "ui" / "qml"
MAIN_QML = QML_DIR / "Main.qml"


def run(argv: list[str]) -> int:
    """Create the Qt application, load ``Main.qml``, and run the event loop.

    Returns the process exit code. Returns a non-zero code *without*
    starting the event loop if the QML fails to load, so a packaging or CI
    smoke test can detect a broken UI without a human watching a window
    appear (see the Phase 1 acceptance check in
    ``ScreenCare — Implementation Standards.md``, section 49).
    """
    app = QGuiApplication(argv)
    app.setOrganizationName("Pivotly")
    app.setApplicationName("ScreenCare")

    engine = QQmlApplicationEngine()
    engine.addImportPath(str(QML_DIR))
    engine.load(QUrl.fromLocalFile(str(MAIN_QML)))

    if not engine.rootObjects():
        logger.error("Failed to load root QML file: %s", MAIN_QML)
        return 1

    return app.exec()


if __name__ == "__main__":
    sys.exit(run(sys.argv))
