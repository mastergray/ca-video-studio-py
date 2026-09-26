from __future__ import annotations  # Enable forward references in type annotations

from pathlib import Path  # Represent project and render destinations

import numpy as np  # Describe RGB frames displayed by the preview
from PySide6.QtCore import Qt, QThread, QTimer  # Schedule preview and background work
from PySide6.QtGui import QAction, QCloseEvent  # Define menu actions and close handling
from PySide6.QtWidgets import (  # Build native window controls and dialogs
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ca_video.config.models import ConfigError, ProjectConfig, loadProject  # Load validated projects
from ca_video.services.runtime import ProjectRuntime  # Drive deterministic preview frames
from ca_video.ui.preview_widget import PreviewWidget  # Display RGB preview frames
from ca_video.ui.render_worker import RenderWorker  # Export video outside the GUI thread


# Hosts the native preview, transport controls, and background render workflow
class MainWindow(QMainWindow):

    # CONSTRUCTOR :: projectConfig -> mainWindow
    # Creates the primary application window for a project
    def __init__(self, project: ProjectConfig) -> None:
        super().__init__()
        self._project = project
        self._runtime = ProjectRuntime(project)
        self._frameIndex = 0
        self._renderThread: QThread | None = None
        self._renderWorker: RenderWorker | None = None

        self.setWindowTitle(f"CA Video — {project.name}")
        self.resize(1180, 760)
        self._buildUi()
        self._buildMenu()

        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._advancePreview)
        self._configureTimer()
        self._showFrame(self._runtime.renderFrame(0))

    #
    # Properties
    #

    # PROPERTY :: VOID -> projectConfig
    # Returns the active project
    @property
    def project(self) -> ProjectConfig:
        return self._project

    # PROPERTY :: VOID -> projectRuntime
    # Returns the active preview runtime
    @property
    def runtime(self) -> ProjectRuntime:
        return self._runtime

    # PROPERTY :: VOID -> INT
    # Returns the displayed frame index
    @property
    def frameIndex(self) -> int:
        return self._frameIndex

    # PROPERTY :: VOID -> previewWidget
    # Returns the central preview widget for integration tests
    @property
    def preview(self) -> PreviewWidget:
        return self._preview

    #
    # Instance Methods
    #

    # :: qCloseEvent -> NONE
    # Cancels active background work before Qt closes the window
    # NOTE: The name is fixed by the Qt override contract
    def closeEvent(self, event: QCloseEvent) -> None:
        if self._renderWorker and self._renderThread:
            response = QMessageBox.question(
                self,
                "Render In Progress",
                "Cancel the active render and quit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if response != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._renderWorker.requestCancel()
            self._renderThread.quit()
            if not self._renderThread.wait(5000):
                self.statusBar().showMessage("Waiting for render worker to stop…")
                event.ignore()
                return
        event.accept()

    #
    # Protected Methods
    #

    # :: VOID -> NONE
    # Builds the preview, controls, status, and progress layout
    def _buildUi(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(12, 12, 12, 12)

        self._preview = PreviewWidget()
        layout.addWidget(self._preview, 1)

        controls = QHBoxLayout()
        self._playButton = QPushButton("Play")
        self._playButton.clicked.connect(self._togglePlay)
        self._stepButton = QPushButton("Step")
        self._stepButton.clicked.connect(self._stepPreview)
        self._resetButton = QPushButton("Reset")
        self._resetButton.clicked.connect(self._resetPreview)
        self._renderButton = QPushButton("Render MP4…")
        self._renderButton.clicked.connect(self._chooseRenderPath)
        self._cancelButton = QPushButton("Cancel Render")
        self._cancelButton.setEnabled(False)
        self._cancelButton.clicked.connect(self._cancelRender)
        for button in (self._playButton, self._stepButton, self._resetButton):
            controls.addWidget(button)
        controls.addStretch(1)
        controls.addWidget(self._renderButton)
        controls.addWidget(self._cancelButton)
        layout.addLayout(controls)

        self._infoLabel = QLabel()
        self._infoLabel.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._infoLabel)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)
        self.setCentralWidget(root)
        self.statusBar().showMessage("Ready")

    # :: VOID -> NONE
    # Builds the native File menu
    def _buildMenu(self) -> None:
        fileMenu = self.menuBar().addMenu("&File")
        openAction = QAction("&Open Project…", self)
        openAction.setShortcut("Ctrl+O")
        openAction.triggered.connect(self._openProject)
        fileMenu.addAction(openAction)
        fileMenu.addSeparator()
        quitAction = QAction("&Quit", self)
        quitAction.setShortcut("Ctrl+Q")
        quitAction.triggered.connect(self.close)
        fileMenu.addAction(quitAction)

    # :: VOID -> NONE
    # Synchronizes preview timing with project fps
    def _configureTimer(self) -> None:
        self._timer.setInterval(max(1, round(1000 / self._project.output.fps)))

    # :: ndarray -> NONE
    # Displays a frame and refreshes preview statistics
    def _showFrame(self, frame: np.ndarray) -> None:
        self._preview.setFrame(frame)
        engine = self._runtime.engine
        density = engine.liveCount / engine.grid.size * 100
        self._infoLabel.setText(
            f"Frame {self._frameIndex}/{self._project.output.totalFrames - 1}  ·  "
            f"Generation {engine.generation}  ·  {engine.liveCount:,} live cells  ·  "
            f"{density:.1f}%  ·  {self._project.output.width}×{self._project.output.height} @ "
            f"{self._project.output.fps} fps"
        )

    # :: VOID -> NONE
    # Starts or pauses preview playback
    def _togglePlay(self) -> None:
        if self._timer.isActive():
            self._timer.stop()
            self._playButton.setText("Play")
        else:
            if self._frameIndex >= self._project.output.totalFrames - 1:
                self._resetPreview()
            self._timer.start()
            self._playButton.setText("Pause")

    # :: VOID -> NONE
    # Advances preview playback by one output frame
    def _advancePreview(self) -> None:
        if self._frameIndex >= self._project.output.totalFrames - 1:
            self._timer.stop()
            self._playButton.setText("Play")
            return
        self._frameIndex += 1
        self._showFrame(self._runtime.renderFrame(self._frameIndex))

    # :: VOID -> NONE
    # Advances the preview by exactly one automaton generation
    def _stepPreview(self) -> None:
        self._timer.stop()
        self._playButton.setText("Play")
        frame = self._runtime.stepOnce()
        self._frameIndex = self._runtime.currentFrameIndex
        self._showFrame(frame)

    # :: VOID -> NONE
    # Restores the deterministic initial preview frame
    def _resetPreview(self) -> None:
        self._timer.stop()
        self._playButton.setText("Play")
        self._runtime.reset()
        self._frameIndex = 0
        self._showFrame(self._runtime.renderFrame(0))

    # :: VOID -> NONE
    # Prompts for and loads a project file
    def _openProject(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Open CA Video Project",
            "",
            "CA Video Projects (*.cav.json);;JSON (*.json)",
        )
        if not selected:
            return
        try:
            project = loadProject(selected)
        except ConfigError as error:
            QMessageBox.critical(self, "Invalid Project", str(error))
            return
        self._timer.stop()
        self._project = project
        self._runtime = ProjectRuntime(project)
        self._frameIndex = 0
        self._configureTimer()
        self.setWindowTitle(f"CA Video — {project.name}")
        self._showFrame(self._runtime.renderFrame(0))
        self.statusBar().showMessage(f"Opened {selected}", 5000)

    # :: VOID -> NONE
    # Prompts for an MP4 destination and confirms replacement
    def _chooseRenderPath(self) -> None:
        suggested = str(self._project.outputPath())
        selected, _ = QFileDialog.getSaveFileName(
            self,
            "Render MP4",
            suggested,
            "MP4 Video (*.mp4)",
        )
        if not selected:
            return
        destination = Path(selected)
        if destination.suffix.lower() != ".mp4":
            destination = destination.with_suffix(".mp4")
        overwrite = False
        if destination.exists():
            response = QMessageBox.question(
                self,
                "Replace Existing Video?",
                f"Replace {destination}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if response != QMessageBox.StandardButton.Yes:
                return
            overwrite = True
        self._startRender(destination, overwrite)

    # :: path, BOOL -> NONE
    # Starts a background render job
    def _startRender(self, destination: Path, overwrite: bool) -> None:
        if self._renderThread is not None:
            return
        self._renderButton.setEnabled(False)
        self._cancelButton.setEnabled(True)
        self._progress.setRange(0, self._project.output.totalFrames)
        self._progress.setValue(0)
        self._progress.setVisible(True)
        self.statusBar().showMessage(f"Rendering {destination}…")

        thread = QThread(self)
        worker = RenderWorker(self._project, destination, overwrite)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._progress.setValue)
        worker.completed.connect(self._renderCompleted)
        worker.cancelled.connect(self._renderCancelled)
        worker.failed.connect(self._renderFailed)
        worker.completed.connect(thread.quit)
        worker.cancelled.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.completed.connect(worker.deleteLater)
        worker.cancelled.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(self._renderThreadFinished)
        thread.finished.connect(thread.deleteLater)
        self._renderThread = thread
        self._renderWorker = worker
        thread.start()

    # :: VOID -> NONE
    # Requests cancellation of the active render
    def _cancelRender(self) -> None:
        if self._renderWorker:
            self._renderWorker.requestCancel()
            self._cancelButton.setEnabled(False)
            self.statusBar().showMessage("Cancelling render…")

    # :: STRING -> NONE
    # Reports successful render completion
    def _renderCompleted(self, path: str) -> None:
        self.statusBar().showMessage(f"Rendered {path}", 10000)
        QMessageBox.information(self, "Render Complete", f"Video written to:\n{path}")

    # :: VOID -> NONE
    # Reports render cancellation
    def _renderCancelled(self) -> None:
        self.statusBar().showMessage("Render cancelled", 5000)

    # :: STRING -> NONE
    # Reports render failure
    def _renderFailed(self, message: str) -> None:
        self.statusBar().showMessage("Render failed", 5000)
        QMessageBox.critical(self, "Render Failed", message)

    # :: VOID -> NONE
    # Releases background job references after thread shutdown
    def _renderThreadFinished(self) -> None:
        self._renderThread = None
        self._renderWorker = None
        self._renderButton.setEnabled(True)
        self._cancelButton.setEnabled(False)
