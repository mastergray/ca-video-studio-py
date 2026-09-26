from __future__ import annotations  # Enable forward references in type annotations

import threading  # Share a cancellation flag safely across Qt threads
from pathlib import Path  # Represent the selected output destination

from PySide6.QtCore import QObject, Signal, Slot  # Run renders and report state through Qt

from ca_video.config.models import ProjectConfig  # Carry an immutable-by-convention project snapshot
from ca_video.encoding.ffmpeg import RenderCancelled, renderProject  # Export MP4 video


# Executes one render job outside the Qt GUI thread
class RenderWorker(QObject):

    # Class Variables
    progress = Signal(int, int)
    completed = Signal(str)
    cancelled = Signal()
    failed = Signal(str)

    # CONSTRUCTOR :: projectConfig, path, BOOL -> renderWorker
    # Creates a cancellable render worker
    def __init__(self, project: ProjectConfig, destination: Path, overwrite: bool) -> None:
        super().__init__()
        self._project = project
        self._destination = destination
        self._overwrite = overwrite
        self._cancelEvent = threading.Event()

    #
    # Instance Methods
    #

    # :: VOID -> NONE
    # Requests cooperative cancellation from any thread
    def requestCancel(self) -> None:
        self._cancelEvent.set()

    # :: VOID -> NONE
    # Runs the render and emits exactly one terminal signal
    @Slot()
    def run(self) -> None:
        try:
            result = renderProject(
                self._project,
                self._destination,
                overwrite=self._overwrite,
                progress=lambda done, total: self.progress.emit(done, total),
                cancelled=self._cancelEvent.is_set,
            )
        except RenderCancelled:
            self.cancelled.emit()
        except Exception as error:
            self.failed.emit(str(error))
        else:
            self.completed.emit(str(result))
