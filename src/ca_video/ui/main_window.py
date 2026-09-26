from __future__ import annotations  # Enable forward references in type annotations

from copy import deepcopy  # Duplicate nested layer mappings safely
from pathlib import Path  # Represent project and render destinations

import numpy as np  # Describe RGB frames displayed by the preview
from PySide6.QtCore import Qt, QThread, QTimer  # Schedule preview and background work
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence  # Define actions and close handling
from PySide6.QtWidgets import (  # Build the native three-pane editor
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ca_video.config.models import (  # Load, validate, and persist projects
    ConfigError,
    ProjectConfig,
    defaultProject,
    loadProject,
    parseProject,
    saveProject,
)
from ca_video.services.runtime import ProjectRuntime  # Drive deterministic preview frames
from ca_video.ui.preview_widget import PreviewWidget  # Display RGB preview frames
from ca_video.ui.property_inspector import PropertyInspector  # Edit supported project settings
from ca_video.ui.render_worker import RenderWorker  # Export video outside the GUI thread

PROJECT_FILTER = "CA Video Projects (*.cav.json);;JSON (*.json)"
PREVIEW_WIDTH = 640
PREVIEW_HEIGHT = 360
PREVIEW_FPS = 30


# Hosts the native editor, preview controls, persistence, and render workflow
class MainWindow(QMainWindow):

    # CONSTRUCTOR :: projectConfig, path? -> mainWindow
    # Creates the primary application window for a project
    def __init__(self, project: ProjectConfig, projectPath: Path | None = None) -> None:
        super().__init__()
        self._project = project
        self._projectPath = projectPath.resolve() if projectPath else None
        self._runtime = ProjectRuntime(project, self._previewSize(project))
        self._frameIndex = 0
        self._previewTick = 0
        self._dirty = False
        self._previewOnly = False
        self._loadingUi = False
        self._selectedLayerIndex = 0
        self._renderThread: QThread | None = None
        self._renderWorker: RenderWorker | None = None

        self.resize(1280, 760)
        self.setMinimumSize(960, 600)
        self._buildUi()
        self._buildActions()
        self._buildMenu()
        self._buildToolbar()
        self._applyTheme()

        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._advancePreview)
        self._configureTimer()
        self._loadUiFromProject()
        self._showFrame(self._runtime.renderAtTick(0, PREVIEW_FPS))
        self._updateTitle()

    #
    # Properties
    #

    # PROPERTY :: VOID -> projectConfig
    # Returns the active project
    @property
    def project(self) -> ProjectConfig:
        return self._project

    # PROPERTY :: VOID -> path?
    # Returns the current project file path
    @property
    def projectPath(self) -> Path | None:
        return self._projectPath

    # PROPERTY :: VOID -> BOOL
    # Returns whether the project has unsaved changes
    @property
    def dirty(self) -> bool:
        return self._dirty

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

    # PROPERTY :: VOID -> propertyInspector
    # Returns the editor inspector for integration tests
    @property
    def inspector(self) -> PropertyInspector:
        return self._inspector

    #
    # Instance Methods
    #

    # :: qCloseEvent -> NONE
    # Confirms unsaved work and cancels active background work before closing
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
        if not self._confirmUnsavedChanges():
            event.ignore()
            return
        event.accept()

    #
    # Protected Methods
    #

    # :: VOID -> NONE
    # Builds the layers, preview, inspector, and diagnostics regions
    def _buildUi(self) -> None:
        root = QWidget()
        rootLayout = QVBoxLayout(root)
        rootLayout.setContentsMargins(10, 10, 10, 6)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._layerPanel = self._buildLayerPanel()
        center = self._buildPreviewPanel()
        self._inspector = PropertyInspector()
        self._inspector.setMinimumWidth(320)
        self._inspector.edited.connect(self._applyEditorData)
        self._inspector.validationError.connect(self._showValidationError)
        self._splitter.addWidget(self._layerPanel)
        self._splitter.addWidget(center)
        self._splitter.addWidget(self._inspector)
        self._splitter.setSizes([210, 700, 330])
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setStretchFactor(2, 0)
        rootLayout.addWidget(self._splitter, 1)

        self._diagnostics = QLabel("✓ Project is valid")
        self._diagnostics.setObjectName("diagnostics")
        rootLayout.addWidget(self._diagnostics)
        self.setCentralWidget(root)
        self.statusBar().showMessage("Ready")

    # :: VOID -> widget
    # Builds the single-layer milestone pane
    def _buildLayerPanel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("sidePanel")
        panel.setMinimumWidth(180)
        panel.setMaximumWidth(300)
        layout = QVBoxLayout(panel)
        title = QLabel("LAYERS")
        title.setObjectName("panelTitle")
        layout.addWidget(title)
        self._layerList = QListWidget()
        self._layerList.setObjectName("layerList")
        self._layerList.itemChanged.connect(self._layerItemChanged)
        self._layerList.currentRowChanged.connect(self._layerSelectionChanged)
        layout.addWidget(self._layerList, 1)
        self._addLayerButton = QPushButton("+ Add 2D Layer")
        self._addLayerButton.clicked.connect(self._addLayer)
        layout.addWidget(self._addLayerButton)
        self._duplicateLayerButton = QPushButton("Duplicate")
        self._duplicateLayerButton.clicked.connect(self._duplicateLayer)
        layout.addWidget(self._duplicateLayerButton)
        orderControls = QHBoxLayout()
        self._moveUpButton = QPushButton("↑")
        self._moveUpButton.setToolTip("Move layer up and composite it later")
        self._moveUpButton.clicked.connect(lambda: self._moveLayer(-1))
        self._moveDownButton = QPushButton("↓")
        self._moveDownButton.clicked.connect(lambda: self._moveLayer(1))
        self._deleteLayerButton = QPushButton("Delete")
        self._deleteLayerButton.clicked.connect(self._deleteLayer)
        orderControls.addWidget(self._moveUpButton)
        orderControls.addWidget(self._moveDownButton)
        orderControls.addWidget(self._deleteLayerButton)
        layout.addLayout(orderControls)
        return panel

    # :: VOID -> widget
    # Builds the central preview, transport, HUD, and render progress
    def _buildPreviewPanel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 0, 8, 0)
        self._preview = PreviewWidget()
        layout.addWidget(self._preview, 1)

        controls = QHBoxLayout()
        self._playButton = QPushButton("▶ Play")
        self._playButton.clicked.connect(self._togglePlay)
        self._stepButton = QPushButton("Step")
        self._stepButton.clicked.connect(self._stepPreview)
        self._resetButton = QPushButton("Reset")
        self._resetButton.clicked.connect(self._resetPreview)
        for button in (self._playButton, self._stepButton, self._resetButton):
            controls.addWidget(button)
        controls.addStretch(1)
        self._timeLabel = QLabel()
        controls.addWidget(self._timeLabel)
        layout.addLayout(controls)

        self._infoLabel = QLabel()
        self._infoLabel.setObjectName("hud")
        self._infoLabel.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._infoLabel)
        self._formatLabel = QLabel()
        self._formatLabel.setObjectName("hud")
        self._formatLabel.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._formatLabel)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)
        return panel

    # :: VOID -> NONE
    # Creates shared actions and keyboard shortcuts
    def _buildActions(self) -> None:
        self._newAction = QAction("&New Project", self)
        self._newAction.setShortcut(QKeySequence.StandardKey.New)
        self._newAction.triggered.connect(self._newProject)
        self._openAction = QAction("&Open Project…", self)
        self._openAction.setShortcut(QKeySequence.StandardKey.Open)
        self._openAction.triggered.connect(self._openProject)
        self._saveAction = QAction("&Save", self)
        self._saveAction.setShortcut(QKeySequence.StandardKey.Save)
        self._saveAction.triggered.connect(self._saveProject)
        self._saveAsAction = QAction("Save &As…", self)
        self._saveAsAction.setShortcut(QKeySequence.StandardKey.SaveAs)
        self._saveAsAction.triggered.connect(self._saveProjectAs)
        self._previewOnlyAction = QAction("Preview &Only", self)
        self._previewOnlyAction.setCheckable(True)
        self._previewOnlyAction.setShortcut("Tab")
        self._previewOnlyAction.triggered.connect(self._togglePreviewOnly)
        self._fullScreenAction = QAction("&Full Screen", self)
        self._fullScreenAction.setCheckable(True)
        self._fullScreenAction.setShortcut("F11")
        self._fullScreenAction.triggered.connect(self._toggleFullScreen)
        self._exitPresentationAction = QAction("Exit Presentation", self)
        self._exitPresentationAction.setShortcut("Escape")
        self._exitPresentationAction.triggered.connect(self._exitPresentation)
        self._playAction = QAction("Play/Pause", self)
        self._playAction.setShortcut("Space")
        self._playAction.triggered.connect(self._togglePlay)
        self._resetAction = QAction("Reset", self)
        self._resetAction.setShortcut("Ctrl+R")
        self._resetAction.triggered.connect(self._resetPreview)
        self._renderAction = QAction("Render Video…", self)
        self._renderAction.setShortcut("Ctrl+Shift+R")
        self._renderAction.triggered.connect(self._chooseRenderPath)
        self._cancelRenderAction = QAction("Cancel Render", self)
        self._cancelRenderAction.setEnabled(False)
        self._cancelRenderAction.triggered.connect(self._cancelRender)
        self.addActions(
            (
                self._previewOnlyAction,
                self._fullScreenAction,
                self._exitPresentationAction,
                self._playAction,
                self._resetAction,
            )
        )

    # :: VOID -> NONE
    # Builds native application menus
    def _buildMenu(self) -> None:
        fileMenu = self.menuBar().addMenu("&File")
        fileMenu.addActions((self._newAction, self._openAction, self._saveAction, self._saveAsAction))
        fileMenu.addSeparator()
        quitAction = QAction("&Quit", self)
        quitAction.setShortcut(QKeySequence.StandardKey.Quit)
        quitAction.triggered.connect(self.close)
        fileMenu.addAction(quitAction)

        viewMenu = self.menuBar().addMenu("&View")
        viewMenu.addActions((self._previewOnlyAction, self._fullScreenAction))
        playbackMenu = self.menuBar().addMenu("&Playback")
        playbackMenu.addActions((self._playAction, self._resetAction))
        renderMenu = self.menuBar().addMenu("&Render")
        renderMenu.addActions((self._renderAction, self._cancelRenderAction))

    # :: VOID -> NONE
    # Builds the compact primary-action toolbar
    def _buildToolbar(self) -> None:
        self._toolbar = QToolBar("Main", self)
        self._toolbar.setMovable(False)
        self._toolbar.addActions((self._newAction, self._openAction, self._saveAction))
        self._toolbar.addSeparator()
        self._toolbar.addAction(self._previewOnlyAction)
        self._toolbar.addSeparator()
        self._toolbar.addAction(self._renderAction)
        self.addToolBar(self._toolbar)

    # :: VOID -> NONE
    # Applies the reference-inspired dark native visual language
    def _applyTheme(self) -> None:
        self.setStyleSheet(
            "QMainWindow, QWidget { background: #0e1214; color: #ccd6d8; }"
            "QMenuBar, QMenu, QToolBar, QStatusBar { background: #141819; color: #ccd6d8; }"
            "QToolBar { border-bottom: 1px solid #263032; spacing: 5px; padding: 4px; }"
            "QPushButton, QToolButton { background: #1e2526; border: 1px solid #303a3c; "
            "border-radius: 4px; padding: 5px 10px; }"
            "QPushButton:hover, QToolButton:hover { border-color: #3ac5c9; }"
            "QPushButton:disabled { color: #536164; }"
            "QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit, QListWidget { "
            "background: #181d1e; border: 1px solid #303a3c; border-radius: 3px; padding: 4px; }"
            "QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, "
            "QPlainTextEdit:focus { border-color: #3ac5c9; }"
            "QTabWidget::pane, QGroupBox { border: 1px solid #263032; }"
            "QTabBar::tab { background: #181d1e; padding: 7px 14px; }"
            "QTabBar::tab:selected { color: #3ac5c9; border-bottom: 2px solid #3ac5c9; }"
            "QGroupBox { margin-top: 10px; padding-top: 8px; font-weight: 600; }"
            "QGroupBox::title { color: #3ac5c9; subcontrol-origin: margin; left: 8px; }"
            "QLabel#panelTitle { color: #3ac5c9; font-weight: 700; letter-spacing: 2px; }"
            "QLabel#hud, QLabel#diagnostics { color: #839194; padding: 4px; }"
            "QListWidget::item:selected { background: #214247; color: #e6f0f0; }"
            "QSplitter::handle { background: #263032; width: 1px; }"
        )

    # :: VOID -> NONE
    # Loads the active model into layer and inspector widgets
    def _loadUiFromProject(self) -> None:
        self._loadingUi = True
        self._layerList.clear()
        self._selectedLayerIndex = min(self._selectedLayerIndex, len(self._project.layers) - 1)
        for layer in self._project.layers:
            item = QListWidgetItem(f"{layer.name}    2D")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if layer.enabled else Qt.CheckState.Unchecked)
            self._layerList.addItem(item)
        self._layerList.setCurrentRow(self._selectedLayerIndex)
        self._inspector.setProject(self._project, self._selectedLayerIndex)
        self._updateLayerActions()
        self._loadingUi = False

    # :: projectConfig -> (INT, INT)
    # Caps preview raster size without enlarging smaller exports
    def _previewSize(self, project: ProjectConfig) -> tuple[int, int]:
        return min(project.output.width, PREVIEW_WIDTH), min(project.output.height, PREVIEW_HEIGHT)

    # :: projectConfig? -> INT
    # Calculates preview samples needed to cover the project duration
    def _previewFrameCount(self, project: ProjectConfig | None = None) -> int:
        selected = project or self._project
        numerator = selected.output.totalFrames * PREVIEW_FPS
        return max(1, (numerator + selected.output.fps - 1) // selected.output.fps)

    # :: VOID -> NONE
    # Uses a fixed preview clock independent of export fps
    def _configureTimer(self) -> None:
        self._timer.setInterval(round(1000 / PREVIEW_FPS))

    # :: ndarray -> NONE
    # Displays a frame and refreshes preview statistics
    def _showFrame(self, frame: np.ndarray) -> None:
        self._preview.setFrame(frame)
        layer = self._project.layers[self._selectedLayerIndex]
        engine = self._runtime.engineForLayer(self._selectedLayerIndex)
        density = engine.liveCount / engine.grid.size * 100
        duration = self._project.output.durationSeconds
        currentSeconds = self._previewTick / PREVIEW_FPS
        self._timeLabel.setText(f"{currentSeconds:06.2f} / {duration:06.2f} s")
        self._infoLabel.setText(
            f"Gen {engine.generation}  ·  {engine.liveCount:,} live  ·  {density:.1f}%  ·  "
            f"{layer.name}  ·  {layer.gridWidth}×{layer.gridHeight}  ·  {layer.rule.notation}"
        )
        self._formatLabel.setText(
            f"Preview {self._runtime.renderSize[0]}×{self._runtime.renderSize[1]} @ {PREVIEW_FPS}  ·  "
            f"Export {self._project.output.width}×{self._project.output.height} @ {self._project.output.fps}"
        )

    # :: VOID -> NONE
    # Starts or pauses preview playback
    def _togglePlay(self) -> None:
        if self._timer.isActive():
            self._pausePreview()
        else:
            if self._previewTick >= self._previewFrameCount() - 1:
                self._resetPreview()
            self._timer.start()
            self._playButton.setText("❚❚ Pause")

    # :: VOID -> NONE
    # Pauses preview playback and normalizes transport labels
    def _pausePreview(self) -> None:
        self._timer.stop()
        self._playButton.setText("▶ Play")

    # :: VOID -> NONE
    # Advances preview playback by one fixed-rate preview tick
    def _advancePreview(self) -> None:
        if self._previewTick >= self._previewFrameCount() - 1:
            self._pausePreview()
            return
        self._previewTick += 1
        self._frameIndex = (self._previewTick * self._project.output.fps) // PREVIEW_FPS
        self._showFrame(self._runtime.renderAtTick(self._previewTick, PREVIEW_FPS))

    # :: VOID -> NONE
    # Advances the preview by exactly one automaton generation
    def _stepPreview(self) -> None:
        self._pausePreview()
        frame = self._runtime.stepOnce()
        self._frameIndex = self._runtime.currentFrameIndex
        self._previewTick = (
            self._frameIndex * PREVIEW_FPS + self._project.output.fps - 1
        ) // self._project.output.fps
        self._showFrame(frame)

    # :: VOID -> NONE
    # Restores the deterministic initial preview frame
    def _resetPreview(self) -> None:
        self._pausePreview()
        self._runtime.reset()
        self._frameIndex = 0
        self._previewTick = 0
        self._showFrame(self._runtime.renderAtTick(0, PREVIEW_FPS))

    # :: object, BOOL -> NONE
    # Validates inspector edits and updates the shared runtime
    def _applyEditorData(self, data: object, resetSimulation: bool) -> None:
        try:
            if not isinstance(data, dict):
                raise ConfigError("editor produced an invalid project mapping")
            project = parseProject(data, self._project.baseDir)
        except ConfigError as error:
            self._showValidationError(str(error))
            return
        self._pausePreview()
        try:
            if resetSimulation:
                runtime = ProjectRuntime(project, self._previewSize(project))
                self._previewTick = 0
                frame = runtime.renderAtTick(0, PREVIEW_FPS)
            else:
                runtime = self._runtime
                runtime.updateProject(project, False, self._previewSize(project))
                self._previewTick = min(self._previewTick, self._previewFrameCount(project) - 1)
                frame = runtime.renderAtTick(self._previewTick, PREVIEW_FPS)
        except ValueError as error:
            self._showValidationError(str(error))
            return
        self._runtime = runtime
        self._project = project
        self._frameIndex = self._runtime.currentFrameIndex
        if resetSimulation:
            self._frameIndex = 0
            self.statusBar().showMessage("Simulation reset after settings change", 3000)
        self._setDirty(True)
        self._diagnostics.setText("✓ Project is valid")
        self._diagnostics.setStyleSheet("color: #7abf6e;")
        self._configureTimer()
        self._refreshLayerItems()
        self._showFrame(frame)

    # :: STRING -> NONE
    # Displays non-blocking editor validation feedback
    def _showValidationError(self, message: str) -> None:
        self._diagnostics.setText(f"⚠ {message}")
        self._diagnostics.setStyleSheet("color: #d98585;")
        self.statusBar().showMessage("Project settings need attention", 3000)

    # :: listWidgetItem -> NONE
    # Applies the layer row's enabled state
    def _layerItemChanged(self, item: QListWidgetItem) -> None:
        if self._loadingUi:
            return
        layerIndex = self._layerList.row(item)
        data = self._project.toDict()
        data["layers"][layerIndex]["enabled"] = item.checkState() == Qt.CheckState.Checked
        self._applyEditorData(data, True)
        self._inspector.setProject(self._project, self._selectedLayerIndex)

    # :: INT -> NONE
    # Selects a layer and loads its contextual inspector values
    def _layerSelectionChanged(self, layerIndex: int) -> None:
        if self._loadingUi or layerIndex < 0:
            return
        self._selectedLayerIndex = layerIndex
        self._inspector.setProject(self._project, layerIndex)
        self._updateLayerActions()
        self._showFrame(self._runtime.renderAtTick(self._previewTick, PREVIEW_FPS))

    # :: VOID -> NONE
    # Refreshes all layer rows after inspector edits
    def _refreshLayerItems(self) -> None:
        self._loadingUi = True
        for layerIndex, layer in enumerate(self._project.layers):
            item = self._layerList.item(layerIndex)
            if item is None:
                continue
            item.setText(f"{layer.name}    2D")
            item.setCheckState(Qt.CheckState.Checked if layer.enabled else Qt.CheckState.Unchecked)
        self._loadingUi = False

    # :: VOID -> NONE
    # Adds a default independently seeded 2D layer at the top of the stack
    def _addLayer(self) -> None:
        data = self._project.toDict()
        layerNumber = len(data["layers"]) + 1
        layerData = defaultProject(self._project.baseDir).toDict()["layers"][0]
        layerData["id"] = self._uniqueLayerId(f"layer_{layerNumber}")
        layerData["name"] = f"Layer {layerNumber}"
        layerData["render"]["color"] = "#3ac5c9"
        data["layers"].insert(0, layerData)
        self._normalizeLayerOrder(data)
        self._selectedLayerIndex = 0
        self._applyEditorData(data, True)
        self._loadUiFromProject()

    # :: VOID -> NONE
    # Duplicates the selected layer with a fresh stable identifier
    def _duplicateLayer(self) -> None:
        data = self._project.toDict()
        source = data["layers"][self._selectedLayerIndex]
        duplicate = deepcopy(source)
        duplicate["id"] = self._uniqueLayerId(f"{source['id']}_copy")
        duplicate["name"] = f"{source['name']} Copy"
        data["layers"].insert(self._selectedLayerIndex, duplicate)
        self._normalizeLayerOrder(data)
        self._applyEditorData(data, True)
        self._loadUiFromProject()

    # :: VOID -> NONE
    # Deletes the selected layer while preserving the one-layer minimum
    def _deleteLayer(self) -> None:
        if len(self._project.layers) <= 1:
            return
        data = self._project.toDict()
        del data["layers"][self._selectedLayerIndex]
        self._selectedLayerIndex = min(self._selectedLayerIndex, len(data["layers"]) - 1)
        self._normalizeLayerOrder(data)
        self._applyEditorData(data, True)
        self._loadUiFromProject()

    # :: INT -> NONE
    # Moves the selected layer through the visual stack
    def _moveLayer(self, offset: int) -> None:
        targetIndex = self._selectedLayerIndex + offset
        if not 0 <= targetIndex < len(self._project.layers):
            return
        data = self._project.toDict()
        layers = data["layers"]
        layers[self._selectedLayerIndex], layers[targetIndex] = layers[targetIndex], layers[self._selectedLayerIndex]
        self._selectedLayerIndex = targetIndex
        self._normalizeLayerOrder(data)
        self._applyEditorData(data, False)
        self._loadUiFromProject()

    # :: STRING -> STRING
    # Produces an unused valid layer identifier
    def _uniqueLayerId(self, base: str) -> str:
        existing = {layer.id for layer in self._project.layers}
        candidate = base[:64]
        suffix = 2
        while candidate in existing:
            ending = f"_{suffix}"
            candidate = f"{base[: 64 - len(ending)]}{ending}"
            suffix += 1
        return candidate

    # :: ARRAY<STRING, object> -> NONE
    # Assigns z-index values so the top row composites last
    def _normalizeLayerOrder(self, data: dict[str, object]) -> None:
        layers = data["layers"]
        layerCount = len(layers)
        for layerIndex, layer in enumerate(layers):
            layer["z_index"] = layerCount - layerIndex - 1

    # :: VOID -> NONE
    # Updates layer operation availability from selection and layer count
    def _updateLayerActions(self) -> None:
        layerCount = len(self._project.layers)
        self._addLayerButton.setEnabled(layerCount < 32)
        self._duplicateLayerButton.setEnabled(layerCount < 32)
        self._moveUpButton.setEnabled(self._selectedLayerIndex > 0)
        self._moveDownButton.setEnabled(self._selectedLayerIndex < layerCount - 1)
        self._deleteLayerButton.setEnabled(layerCount > 1)

    # :: VOID -> NONE
    # Starts a clean default project after confirming unsaved changes
    def _newProject(self) -> None:
        if not self._confirmUnsavedChanges():
            return
        self._adoptProject(defaultProject(), None, False)
        self.statusBar().showMessage("Created a new project", 3000)

    # :: VOID -> NONE
    # Prompts for and loads a project file
    def _openProject(self) -> None:
        if not self._confirmUnsavedChanges():
            return
        selected, _ = QFileDialog.getOpenFileName(self, "Open CA Video Project", "", PROJECT_FILTER)
        if not selected:
            return
        try:
            project = loadProject(selected)
        except ConfigError as error:
            QMessageBox.critical(self, "Invalid Project", str(error))
            return
        self._adoptProject(project, Path(selected), False)
        self.statusBar().showMessage(f"Opened {selected}", 5000)

    # :: VOID -> BOOL
    # Saves to the current path or delegates to Save As
    def _saveProject(self) -> bool:
        if self._projectPath is None:
            return self._saveProjectAs()
        try:
            self._project = saveProject(self._project, self._projectPath)
        except ConfigError as error:
            QMessageBox.critical(self, "Save Failed", str(error))
            return False
        self._runtime.updateProject(self._project, False, self._previewSize(self._project))
        self._inspector.setProject(self._project, self._selectedLayerIndex)
        self._setDirty(False)
        self.statusBar().showMessage(f"Saved {self._projectPath}", 5000)
        return True

    # :: VOID -> BOOL
    # Prompts for a project destination and saves atomically
    def _saveProjectAs(self) -> bool:
        suggested = str(self._projectPath or (self._project.baseDir / "untitled.cav.json"))
        selected, _ = QFileDialog.getSaveFileName(self, "Save CA Video Project", suggested, PROJECT_FILTER)
        if not selected:
            return False
        path = Path(selected)
        if not str(path).lower().endswith(".cav.json"):
            path = path.with_suffix(".cav.json")
        self._projectPath = path.resolve()
        return self._saveProject()

    # :: VOID -> BOOL
    # Offers Save, Discard, or Cancel when the project is dirty
    def _confirmUnsavedChanges(self) -> bool:
        if not self._dirty:
            return True
        response = QMessageBox.warning(
            self,
            "Unsaved Changes",
            "Save changes to this project?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if response == QMessageBox.StandardButton.Cancel:
            return False
        if response == QMessageBox.StandardButton.Save:
            return self._saveProject()
        return True

    # :: projectConfig, path?, BOOL -> NONE
    # Replaces the active project and refreshes every editor region
    def _adoptProject(self, project: ProjectConfig, path: Path | None, dirty: bool) -> None:
        self._pausePreview()
        self._project = project
        self._projectPath = path.resolve() if path else None
        self._selectedLayerIndex = 0
        self._runtime = ProjectRuntime(project, self._previewSize(project))
        self._frameIndex = 0
        self._previewTick = 0
        self._configureTimer()
        self._loadUiFromProject()
        self._showFrame(self._runtime.renderAtTick(0, PREVIEW_FPS))
        self._diagnostics.setText("✓ Project is valid")
        self._diagnostics.setStyleSheet("color: #7abf6e;")
        self._setDirty(dirty)

    # :: BOOL -> NONE
    # Updates dirty state and its title-bar indicator
    def _setDirty(self, dirty: bool) -> None:
        self._dirty = dirty
        self._updateTitle()

    # :: VOID -> NONE
    # Updates the desktop window title from project state
    def _updateTitle(self) -> None:
        marker = " *" if self._dirty else ""
        self.setWindowTitle(f"CA Video — {self._project.name}{marker}")

    # :: VOID -> NONE
    # Enters or exits the distraction-free preview workspace
    def _togglePreviewOnly(self) -> None:
        self._previewOnly = self._previewOnlyAction.isChecked()
        visible = not self._previewOnly
        self._layerPanel.setVisible(visible)
        self._inspector.setVisible(visible)
        self._diagnostics.setVisible(visible)
        self._toolbar.setVisible(visible)
        self.menuBar().setVisible(visible)

    # :: VOID -> NONE
    # Toggles native full-screen presentation
    def _toggleFullScreen(self) -> None:
        if self._fullScreenAction.isChecked():
            self.showFullScreen()
        else:
            self.showNormal()

    # :: VOID -> NONE
    # Leaves full-screen or preview-only presentation state
    def _exitPresentation(self) -> None:
        if self._fullScreenAction.isChecked():
            self._fullScreenAction.setChecked(False)
            self.showNormal()
            return
        if self._previewOnly:
            self._previewOnlyAction.setChecked(False)
            self._togglePreviewOnly()

    # :: VOID -> NONE
    # Prompts for an MP4 destination and confirms replacement
    def _chooseRenderPath(self) -> None:
        suggested = str(self._project.outputPath())
        selected, _ = QFileDialog.getSaveFileName(self, "Render MP4", suggested, "MP4 Video (*.mp4)")
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
    # Starts a background render job from an immutable project snapshot
    def _startRender(self, destination: Path, overwrite: bool) -> None:
        if self._renderThread is not None:
            return
        self._renderAction.setEnabled(False)
        self._cancelRenderAction.setEnabled(True)
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
            self._cancelRenderAction.setEnabled(False)
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
        self._renderAction.setEnabled(True)
        self._cancelRenderAction.setEnabled(False)
