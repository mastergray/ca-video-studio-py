from __future__ import annotations  # Enable forward references in type annotations

import sys  # Provide a minimal argument vector to Qt
from pathlib import Path  # Represent an optional project path

from PySide6.QtCore import QCoreApplication  # Set native application metadata
from PySide6.QtWidgets import QApplication  # Own the desktop event loop

from ca_video.config.models import defaultProject, loadProject  # Load initial project settings
from ca_video.ui.main_window import MainWindow  # Create the primary editor window


# :: STRING|path? -> INT
# Starts the native Qt application and returns its exit status
def runGui(projectPath: str | Path | None = None) -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    QCoreApplication.setOrganizationName("CA Video Studio")
    QCoreApplication.setApplicationName("CA Video Studio (Python)")
    project = loadProject(projectPath) if projectPath else defaultProject()
    resolvedPath = Path(projectPath).expanduser().resolve() if projectPath else None
    window = MainWindow(project, resolvedPath)
    window.show()
    return app.exec()
