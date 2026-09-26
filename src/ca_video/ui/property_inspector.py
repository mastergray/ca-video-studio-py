from __future__ import annotations  # Enable forward references in type annotations

from copy import deepcopy  # Build isolated editable project mappings

from PySide6.QtCore import Qt, QTimer, Signal  # Debounce text edits and publish validated changes
from PySide6.QtGui import QColor  # Convert native color selections
from PySide6.QtWidgets import (  # Build the project and layer inspector forms
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ca_video.catalogs.rules_2d import ruleCatalog  # Populate categorized rule choices
from ca_video.catalogs.rules_3d import palette3DCatalog, rule3DCatalog  # Populate 3D choices
from ca_video.config.models import (  # Present normalized project and layer values
    Layer2DConfig,
    Layer3DConfig,
    ProjectConfig,
    colorToHex,
)
from ca_video.services.runtime import stableLayerSeed  # Display deterministic derived layer seeds

RESOLUTIONS = ((640, 360), (960, 540), (1280, 720), (1920, 1080))
FPS_VALUES = (24, 25, 30, 50, 60)


# Presents a native color picker while retaining a normalized hex value
class ColorButton(QPushButton):

    # Class Variables
    colorChanged = Signal(str)

    # CONSTRUCTOR :: STRING, widget? -> colorButton
    # Creates a compact color selection button
    def __init__(self, color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = color
        self.clicked.connect(self._chooseColor)
        self.setColor(color)

    #
    # Properties
    #

    # PROPERTY :: VOID -> STRING
    # Returns the selected normalized color
    @property
    def color(self) -> str:
        return self._color

    #
    # Instance Methods
    #

    # :: STRING -> NONE
    # Updates the selected color and button swatch
    def setColor(self, color: str) -> None:
        self._color = QColor(color).name()
        self.setText(self._color.upper())
        self.setStyleSheet(
            f"QPushButton {{ background: {self._color}; color: {self._contrastColor()}; "
            "border: 1px solid #536164; padding: 5px; }"
        )

    #
    # Protected Methods
    #

    # :: VOID -> NONE
    # Opens the native color chooser
    def _chooseColor(self) -> None:
        selected = QColorDialog.getColor(QColor(self._color), self, "Choose Color")
        if selected.isValid() and selected.name() != self._color:
            self.setColor(selected.name())
            self.colorChanged.emit(self._color)

    # :: VOID -> STRING
    # Selects legible text for the current swatch
    def _contrastColor(self) -> str:
        color = QColor(self._color)
        luminance = 0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue()
        return "#0e1214" if luminance > 150 else "#f2f7f7"


# Edits the supported single-layer project and emits normalized mappings
class PropertyInspector(QWidget):

    # Class Variables
    edited = Signal(object, bool)
    validationError = Signal(str)

    # CONSTRUCTOR :: widget? -> propertyInspector
    # Creates project and layer forms for the editable 2D milestone
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._project: ProjectConfig | None = None
        self._layerIndex = 0
        self._loading = False
        self._textTimer = QTimer(self)
        self._textTimer.setSingleShot(True)
        self._textTimer.setInterval(350)
        self._textTimer.timeout.connect(lambda: self._emitChange(True))
        self._buildUi()

    #
    # Instance Methods
    #

    # :: projectConfig, INT -> NONE
    # Loads project values without reporting edits
    def setProject(self, project: ProjectConfig, layerIndex: int = 0) -> None:
        self._loading = True
        self._project = project
        self._layerIndex = layerIndex
        layer = project.layers[layerIndex]
        initial = layer.initial

        self._projectName.setText(project.name)
        self._projectSeed.setText(str(project.seed))
        resolutionIndex = self._resolution.findData(f"{project.output.width}x{project.output.height}")
        self._resolution.setCurrentIndex(max(0, resolutionIndex))
        fpsIndex = self._fps.findData(project.output.fps)
        self._fps.setCurrentIndex(max(0, fpsIndex))
        self._duration.setValue(project.output.durationSeconds)
        self._backgroundColor.setColor(colorToHex(project.canvasBackground))

        self._layerName.setText(layer.name)
        seedModeIndex = self._layerSeedMode.findData("custom" if layer.seed is not None else "derived")
        self._layerSeedMode.setCurrentIndex(max(0, seedModeIndex))
        resolvedSeed = layer.seed if layer.seed is not None else stableLayerSeed(project.seed, layer.id)
        self._layerSeed.setText(str(resolvedSeed))
        self._boundary.setCurrentIndex(max(0, self._boundary.findData(layer.boundary)))
        self._density.setValue(initial.density)
        self._radius.setValue(initial.radius)
        self._origin.setCurrentIndex(max(0, self._origin.findData(initial.origin)))
        if isinstance(layer, Layer3DConfig):
            self._rule3D.setCurrentIndex(max(0, self._rule3D.findData(layer.rulePreset)))
            self._gridSize3D.setValue(layer.gridSize)
            self._populateInitialTypes("3d", initial.type)
            self._cells.setPlainText(
                "\n".join(f"{xValue},{yValue},{zValue}" for xValue, yValue, zValue in initial.cells)
            )
            self._cells.setPlaceholderText("One x,y,z voxel coordinate per line")
            self._palette3D.setCurrentIndex(max(0, self._palette3D.findData(layer.palette)))
            self._renderStyle3D.setCurrentIndex(max(0, self._renderStyle3D.findData(layer.renderStyle)))
            self._voxelScale.setValue(layer.voxelScale)
            self._surfaceOnly.setChecked(layer.surfaceOnly)
            self._colorBy.setCurrentIndex(max(0, self._colorBy.findData(layer.colorBy)))
            self._depthShading.setChecked(layer.depthShading)
            self._vignette.setChecked(layer.vignette)
            camera = layer.camera or project.camera
            self._cameraProjection.setCurrentIndex(
                max(0, self._cameraProjection.findData(camera.projection))
            )
            self._azimuth.setValue(camera.azimuthDeg)
            self._elevation.setValue(camera.elevationDeg)
            self._zoom.setValue(camera.zoom)
            self._perspectiveStrength.setValue(camera.perspectiveStrength)
            self._rotationRate.setValue(camera.rotationDegPerSecond)
            self._panX.setValue(camera.panX)
            self._panY.setValue(camera.panY)
        else:
            modeIndex = self._simulationMode.findData(layer.simulationMode)
            self._simulationMode.setCurrentIndex(max(0, modeIndex))
            self._wolframRule.setValue(layer.wolframRule if layer.wolframRule is not None else 30)
            if layer.rule is not None:
                ruleIndex = self._rulePreset.findData(layer.rulePreset or "custom")
                self._rulePreset.setCurrentIndex(max(0, ruleIndex))
                self._customNotation.setText(layer.rule.notation)
                neighborhoodIndex = self._neighborhood.findData(layer.rule.neighborhood)
                self._neighborhood.setCurrentIndex(max(0, neighborhoodIndex))
            gridModeIndex = self._gridMode.findData("cell_size" if layer.cellSizePx is not None else "size")
            self._gridMode.setCurrentIndex(max(0, gridModeIndex))
            self._gridWidth.setValue(layer.gridWidth)
            self._gridHeight.setValue(layer.gridHeight)
            self._cellSize.setValue(layer.cellSizePx or 4)
            self._populateInitialTypes(layer.simulationMode, initial.type)
            self._offsetX.setValue(initial.offsetPx[0])
            self._offsetY.setValue(initial.offsetPx[1])
            self._cells.setPlainText("\n".join(f"{xValue},{yValue}" for xValue, yValue in initial.cells))
            self._cells.setPlaceholderText("One x,y cell coordinate per line")
            rleText = initial.rleData or ""
            if not rleText and initial.rlePath is not None:
                source = initial.rlePath if initial.rlePath.is_absolute() else project.baseDir / initial.rlePath
                try:
                    rleText = source.read_text(encoding="utf-8")
                except OSError:
                    rleText = ""
            self._rle.setPlainText(rleText or "x = 3, y = 3\nbob$2bo$3o!")
            self._bits.setText("".join(str(bit) for bit in initial.bits) or "1")
            self._liveColor.setColor(colorToHex(layer.liveColor))
            self._layout.setCurrentIndex(max(0, self._layout.findData(layer.layout)))

        self._opacity.setValue(layer.opacity)
        self._stepInterval.setValue(layer.stepIntervalMs)
        self._syncDimensionControls()
        self._syncSeedControls()
        self._updateResolvedSeed()
        self._loading = False

    # :: VOID -> ARRAY<STRING, ANY>
    # Builds a project mapping from the current controls
    def projectData(self) -> dict[str, object]:
        if self._project is None:
            raise ValueError("no project is loaded")
        data = deepcopy(self._project.toDict())
        projectData = data["project"]
        outputData = data["output"]
        canvasData = data["canvas"]
        layerData = data["layers"][self._layerIndex]
        simulationData = layerData["simulation"]

        projectData["name"] = self._projectName.text().strip()
        projectData["seed"] = self._seedValue(self._projectSeed, "Project seed")
        width, height = RESOLUTIONS[self._resolution.currentIndex()]
        outputData["width"] = width
        outputData["height"] = height
        outputData["fps"] = self._fps.currentData()
        outputData["duration_seconds"] = self._duration.value()
        canvasData["background"] = self._backgroundColor.color

        layerData["name"] = self._layerName.text().strip()
        if self._layerSeedMode.currentData() == "custom":
            layerData["seed"] = self._seedValue(self._layerSeed, "Layer seed")
        else:
            layerData.pop("seed", None)
        layer = self._project.layers[self._layerIndex]
        if isinstance(layer, Layer3DConfig):
            simulationData["mode"] = "outer_totalistic"
            simulationData["rule"] = {"preset": self._rule3D.currentData()}
            simulationData["grid"] = {
                "grid_size": self._gridSize3D.value(),
                "boundary": self._boundary.currentData(),
            }
            simulationData["initial"] = self._initialData()
            renderStyle = self._renderStyle3D.currentData()
            renderData: dict[str, object] = {
                "style": renderStyle,
                "palette": self._palette3D.currentData(),
                "voxel_scale": self._voxelScale.value() or "auto",
                "surface_only": self._surfaceOnly.isChecked(),
            }
            if renderStyle == "projected_voxel":
                renderData.update(
                    {
                        "color_by": self._colorBy.currentData(),
                        "depth_shading": self._depthShading.isChecked(),
                        "vignette": self._vignette.isChecked(),
                        "camera": {
                            "projection": self._cameraProjection.currentData(),
                            "azimuth_deg": self._azimuth.value(),
                            "elevation_deg": self._elevation.value(),
                            "zoom": self._zoom.value(),
                            "perspective_strength": self._perspectiveStrength.value(),
                            "rotation_deg_per_second": self._rotationRate.value(),
                            "pan_x": self._panX.value(),
                            "pan_y": self._panY.value(),
                        },
                    }
                )
            layerData["render"] = renderData
        else:
            simulationMode = self._simulationMode.currentData()
            simulationData["mode"] = simulationMode
            if simulationMode == "wolfram_2d":
                simulationData["rule"] = {"number": self._wolframRule.value()}
            else:
                ruleKey = self._rulePreset.currentData()
                simulationData["rule"] = (
                    {
                        "notation": self._customNotation.text().strip(),
                        "neighborhood": self._neighborhood.currentData(),
                    }
                    if ruleKey == "custom"
                    else {"preset": ruleKey}
                )
            gridData = {
                "boundary": "wrap" if simulationMode == "wolfram_2d" else self._boundary.currentData()
            }
            if self._gridMode.currentData() == "cell_size":
                gridData["cell_size_px"] = self._cellSize.value()
            else:
                gridData["size"] = [self._gridWidth.value(), self._gridHeight.value()]
            simulationData["grid"] = gridData
            simulationData["initial"] = self._initialData()
            layerData["render"]["color"] = self._liveColor.color
            layerData["render"]["layout"] = self._layout.currentData()
        layerData["opacity"] = self._opacity.value()
        layerData["step_interval_ms"] = self._stepInterval.value()
        return data

    #
    # Protected Methods
    #

    # :: VOID -> NONE
    # Builds the tabbed, scrollable inspector
    def _buildUi(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        tabs = QTabWidget()
        tabs.addTab(self._buildLayerTab(), "Layer")
        tabs.addTab(self._buildProjectTab(), "Project")
        layout.addWidget(tabs)

    # :: VOID -> widget
    # Builds selected-layer settings
    def _buildLayerTab(self) -> QWidget:
        container, content, layout = self._scrollingTab()

        general = QGroupBox("General")
        generalForm = QFormLayout(general)
        self._generalForm = generalForm
        self._layerName = QLineEdit()
        self._layerSeedMode = QComboBox()
        self._layerSeedMode.addItem("Derived from project", "derived")
        self._layerSeedMode.addItem("Custom", "custom")
        self._layerSeed = QLineEdit()
        self._layerSeed.setPlaceholderText("0 to 9223372036854775807")
        self._resolvedSeed = QLabel()
        self._resolvedSeed.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        generalForm.addRow("Name", self._layerName)
        generalForm.addRow("Seed source", self._layerSeedMode)
        generalForm.addRow("Layer seed", self._layerSeed)
        generalForm.addRow("Resolved seed", self._resolvedSeed)
        layout.addWidget(general)

        simulation = QGroupBox("Simulation")
        simulationForm = QFormLayout(simulation)
        self._simulationForm = simulationForm
        self._simulationMode = QComboBox()
        self._simulationMode.addItem("Outer-totalistic 2D", "outer_totalistic")
        self._simulationMode.addItem("Wolfram scrolling history", "wolfram_2d")
        self._rulePreset = QComboBox()
        previousCategory = None
        for entry in ruleCatalog():
            if previousCategory is not None and entry.category != previousCategory:
                self._rulePreset.insertSeparator(self._rulePreset.count())
            self._rulePreset.addItem(f"{entry.name}  ·  {entry.notation}", entry.key)
            self._rulePreset.setItemData(self._rulePreset.count() - 1, entry.description, 3)
            previousCategory = entry.category
        self._rulePreset.insertSeparator(self._rulePreset.count())
        self._rulePreset.addItem("Custom B/S/C rule…", "custom")
        self._rule3D = QComboBox()
        previousCategory = None
        for entry in rule3DCatalog():
            if previousCategory is not None and entry.category != previousCategory:
                self._rule3D.insertSeparator(self._rule3D.count())
            self._rule3D.addItem(f"{entry.name}  ·  {entry.notation}", entry.key)
            self._rule3D.setItemData(self._rule3D.count() - 1, entry.description, 3)
            previousCategory = entry.category
        self._customNotation = QLineEdit("B3/S23")
        self._customNotation.setPlaceholderText("B3/S23 or B2/S/C3")
        self._wolframRule = self._spinBox(0, 255)
        self._wolframRule.setValue(30)
        self._wolframRule.setToolTip("Elementary Wolfram rule number from 0 through 255")
        self._neighborhood = QComboBox()
        self._neighborhood.addItem("Moore (8 neighbors)", "moore")
        self._neighborhood.addItem("von Neumann (4 neighbors)", "von_neumann")
        self._gridMode = QComboBox()
        self._gridMode.addItem("Fixed grid size", "size")
        self._gridMode.addItem("Cell size from export", "cell_size")
        self._gridWidth = self._spinBox(8, 2048)
        self._gridHeight = self._spinBox(8, 2048)
        self._gridSize3D = self._spinBox(8, 80)
        self._cellSize = self._spinBox(1, 128, " px")
        self._derivedGrid = QLabel()
        self._derivedGrid.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._boundary = QComboBox()
        self._boundary.addItem("Wrap", "wrap")
        self._boundary.addItem("Fixed", "fixed")
        simulationForm.addRow("Rule type", self._simulationMode)
        simulationForm.addRow("Rule", self._rulePreset)
        simulationForm.addRow("3D rule", self._rule3D)
        simulationForm.addRow("Notation", self._customNotation)
        simulationForm.addRow("Neighborhood", self._neighborhood)
        simulationForm.addRow("Wolfram rule", self._wolframRule)
        simulationForm.addRow("Grid mode", self._gridMode)
        simulationForm.addRow("Grid width", self._gridWidth)
        simulationForm.addRow("Grid height", self._gridHeight)
        simulationForm.addRow("Cubic grid", self._gridSize3D)
        simulationForm.addRow("Cell size", self._cellSize)
        simulationForm.addRow("Derived grid", self._derivedGrid)
        simulationForm.addRow("Boundary", self._boundary)
        layout.addWidget(simulation)

        initial = QGroupBox("Initial Condition")
        initialForm = QFormLayout(initial)
        self._initialForm = initialForm
        self._initialType = QComboBox()
        self._density = QDoubleSpinBox()
        self._density.setRange(0, 1)
        self._density.setSingleStep(0.05)
        self._density.setDecimals(2)
        self._radius = self._spinBox(1, 2048)
        self._offsetX = self._spinBox(-8192, 8192, " px")
        self._offsetX.setToolTip("Horizontal position relative to the export canvas center")
        self._offsetY = self._spinBox(-8192, 8192, " px")
        self._offsetY.setToolTip("Vertical position relative to the export canvas center")
        self._origin = QComboBox()
        self._origin.addItem("Centered", "center")
        self._origin.addItem("Absolute", "absolute")
        self._cells = QPlainTextEdit()
        self._cells.setPlaceholderText("One x,y coordinate per line")
        self._cells.setMaximumHeight(90)
        self._rle = QPlainTextEdit()
        self._rle.setPlaceholderText("Paste a two-state Life RLE pattern")
        self._rle.setMaximumHeight(110)
        self._bits = QLineEdit("1")
        self._bits.setPlaceholderText("Centered bit pattern, for example 101101")
        initialForm.addRow("Type", self._initialType)
        initialForm.addRow("Density", self._density)
        initialForm.addRow("Radius", self._radius)
        initialForm.addRow("Offset X", self._offsetX)
        initialForm.addRow("Offset Y", self._offsetY)
        initialForm.addRow("Coordinates", self._origin)
        initialForm.addRow("Cells", self._cells)
        initialForm.addRow("RLE", self._rle)
        initialForm.addRow("Bits", self._bits)
        layout.addWidget(initial)

        appearance = QGroupBox("Appearance")
        appearanceForm = QFormLayout(appearance)
        self._appearanceForm = appearanceForm
        self._liveColor = ColorButton("#e8f4ff")
        self._opacity = QDoubleSpinBox()
        self._opacity.setRange(0, 1)
        self._opacity.setSingleStep(0.05)
        self._opacity.setDecimals(2)
        self._layout = QComboBox()
        self._layout.addItem("Fit", "fit")
        self._layout.addItem("Cover", "cover")
        self._renderStyle3D = QComboBox()
        self._renderStyle3D.addItem("Isometric faces", "isometric_voxel")
        self._renderStyle3D.addItem("Camera projected", "projected_voxel")
        self._palette3D = QComboBox()
        for palette in palette3DCatalog():
            self._palette3D.addItem(palette.key.replace("_", " ").title(), palette.key)
        self._voxelScale = self._spinBox(0, 64, " px")
        self._voxelScale.setSpecialValueText("Auto")
        self._surfaceOnly = QCheckBox("Cull fully enclosed voxels")
        self._colorBy = QComboBox()
        self._colorBy.addItem("Fixed palette color", "fixed")
        self._colorBy.addItem("Cell state", "state")
        self._colorBy.addItem("Height", "height")
        self._colorBy.addItem("Distance from center", "distance")
        self._depthShading = QCheckBox("Shade by camera depth")
        self._vignette = QCheckBox("Darken canvas edges")
        appearanceForm.addRow("Live color", self._liveColor)
        appearanceForm.addRow("Opacity", self._opacity)
        appearanceForm.addRow("Layout", self._layout)
        appearanceForm.addRow("3D renderer", self._renderStyle3D)
        appearanceForm.addRow("Face palette", self._palette3D)
        appearanceForm.addRow("Voxel scale", self._voxelScale)
        appearanceForm.addRow("Surface only", self._surfaceOnly)
        appearanceForm.addRow("Color by", self._colorBy)
        appearanceForm.addRow("Depth shading", self._depthShading)
        appearanceForm.addRow("Vignette", self._vignette)
        layout.addWidget(appearance)

        self._cameraGroup = QGroupBox("Camera")
        cameraForm = QFormLayout(self._cameraGroup)
        self._cameraProjection = QComboBox()
        self._cameraProjection.addItem("Perspective", "perspective")
        self._cameraProjection.addItem("Orthographic", "orthographic")
        self._azimuth = self._doubleSpinBox(-360, 360, 1, "°")
        self._elevation = self._doubleSpinBox(-89, 89, 1, "°")
        self._zoom = self._doubleSpinBox(0.1, 10, 0.1, "×")
        self._perspectiveStrength = self._doubleSpinBox(0, 1, 0.05)
        self._rotationRate = self._doubleSpinBox(-360, 360, 1, "°/s")
        self._panX = self._doubleSpinBox(-1, 1, 0.05)
        self._panY = self._doubleSpinBox(-1, 1, 0.05)
        cameraForm.addRow("Projection", self._cameraProjection)
        cameraForm.addRow("Azimuth", self._azimuth)
        cameraForm.addRow("Elevation", self._elevation)
        cameraForm.addRow("Zoom", self._zoom)
        cameraForm.addRow("Perspective", self._perspectiveStrength)
        cameraForm.addRow("Rotation rate", self._rotationRate)
        cameraForm.addRow("Pan X", self._panX)
        cameraForm.addRow("Pan Y", self._panY)
        layout.addWidget(self._cameraGroup)

        timing = QGroupBox("Timing")
        timingForm = QFormLayout(timing)
        self._stepInterval = self._spinBox(1, 60_000, " ms")
        timingForm.addRow("Step interval", self._stepInterval)
        layout.addWidget(timing)
        layout.addStretch(1)

        self._simulationMode.currentIndexChanged.connect(self._simulationModeChanged)
        self._rulePreset.currentIndexChanged.connect(self._ruleChanged)
        self._rule3D.currentIndexChanged.connect(lambda _value: self._emitChange(True))
        self._gridMode.currentIndexChanged.connect(self._gridModeChanged)
        self._initialType.currentIndexChanged.connect(self._initialChanged)
        self._layerSeedMode.currentIndexChanged.connect(self._seedModeChanged)
        self._connectLineEdit(self._layerName, True)
        self._connectLineEdit(self._customNotation, True)
        self._connectLineEdit(self._bits, True)
        self._layerSeed.editingFinished.connect(self._layerSeedEdited)
        for control in (
            self._neighborhood,
            self._wolframRule,
            self._gridWidth,
            self._gridHeight,
            self._gridSize3D,
            self._boundary,
            self._density,
            self._radius,
            self._offsetX,
            self._offsetY,
            self._origin,
            self._stepInterval,
        ):
            control.currentIndexChanged.connect(lambda _value: self._emitChange(True)) if isinstance(
                control, QComboBox
            ) else control.valueChanged.connect(lambda _value: self._emitChange(True))
        self._cellSize.valueChanged.connect(self._cellSizeChanged)
        self._cells.textChanged.connect(self._queueTextChange)
        self._rle.textChanged.connect(self._queueTextChange)
        self._liveColor.colorChanged.connect(lambda _value: self._emitChange(False))
        self._opacity.valueChanged.connect(lambda _value: self._emitChange(False))
        self._layout.currentIndexChanged.connect(self._layoutChanged)
        self._palette3D.currentIndexChanged.connect(lambda _value: self._emitChange(False))
        self._renderStyle3D.currentIndexChanged.connect(self._renderStyleChanged)
        self._voxelScale.valueChanged.connect(lambda _value: self._emitChange(False))
        self._surfaceOnly.toggled.connect(lambda _checked: self._emitChange(False))
        self._colorBy.currentIndexChanged.connect(lambda _value: self._emitChange(False))
        self._depthShading.toggled.connect(lambda _checked: self._emitChange(False))
        self._vignette.toggled.connect(lambda _checked: self._emitChange(False))
        self._cameraProjection.currentIndexChanged.connect(self._cameraProjectionChanged)
        for control in (
            self._azimuth,
            self._elevation,
            self._zoom,
            self._perspectiveStrength,
            self._rotationRate,
            self._panX,
            self._panY,
        ):
            control.valueChanged.connect(lambda _value: self._emitChange(False))
        return container

    # :: VOID -> widget
    # Builds project and output settings
    def _buildProjectTab(self) -> QWidget:
        container, content, layout = self._scrollingTab()

        projectGroup = QGroupBox("Project")
        projectForm = QFormLayout(projectGroup)
        self._projectName = QLineEdit()
        self._projectSeed = QLineEdit()
        self._projectSeed.setPlaceholderText("0 to 9223372036854775807")
        projectForm.addRow("Name", self._projectName)
        projectForm.addRow("Random seed", self._projectSeed)
        layout.addWidget(projectGroup)

        outputGroup = QGroupBox("Output")
        outputForm = QFormLayout(outputGroup)
        self._resolution = QComboBox()
        for width, height in RESOLUTIONS:
            self._resolution.addItem(f"{width} × {height}", f"{width}x{height}")
        self._fps = QComboBox()
        for fps in FPS_VALUES:
            self._fps.addItem(f"{fps} fps", fps)
        self._duration = QDoubleSpinBox()
        self._duration.setRange(0.1, 60)
        self._duration.setDecimals(3)
        self._duration.setSingleStep(0.5)
        self._duration.setSuffix(" s")
        outputForm.addRow("Resolution", self._resolution)
        outputForm.addRow("Frame rate", self._fps)
        outputForm.addRow("Duration", self._duration)
        layout.addWidget(outputGroup)

        canvasGroup = QGroupBox("Canvas")
        canvasForm = QFormLayout(canvasGroup)
        self._backgroundColor = ColorButton("#0d1117")
        canvasForm.addRow("Background", self._backgroundColor)
        layout.addWidget(canvasGroup)
        metadata = QLabel("Schema 1 · H.264 / yuv420p")
        metadata.setObjectName("metadataLabel")
        layout.addWidget(metadata)
        layout.addStretch(1)

        self._connectLineEdit(self._projectName, False)
        self._projectSeed.editingFinished.connect(self._projectSeedEdited)
        self._resolution.currentIndexChanged.connect(self._resolutionChanged)
        self._fps.currentIndexChanged.connect(lambda _value: self._emitChange(False))
        self._duration.valueChanged.connect(lambda _value: self._emitChange(False))
        self._backgroundColor.colorChanged.connect(lambda _value: self._emitChange(False))
        return container

    # :: VOID -> (widget, widget, vBoxLayout)
    # Creates one scrollable tab and its content layout
    def _scrollingTab(self) -> tuple[QWidget, QWidget, QVBoxLayout]:
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(8, 8, 8, 8)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        return container, content, layout

    # :: INT, INT, STRING -> spinBox
    # Creates a consistently configured integer editor
    def _spinBox(self, minimum: int, maximum: int, suffix: str = "") -> QSpinBox:
        control = QSpinBox()
        control.setRange(minimum, maximum)
        control.setSuffix(suffix)
        return control

    # :: FLOAT, FLOAT, FLOAT, STRING -> doubleSpinBox
    # Creates a consistently configured decimal editor
    def _doubleSpinBox(
        self,
        minimum: float,
        maximum: float,
        step: float,
        suffix: str = "",
    ) -> QDoubleSpinBox:
        control = QDoubleSpinBox()
        control.setRange(minimum, maximum)
        control.setSingleStep(step)
        control.setDecimals(2)
        control.setSuffix(suffix)
        return control

    # :: lineEdit, BOOL -> NONE
    # Connects a text field with editing-finished validation
    def _connectLineEdit(self, control: QLineEdit, resetSimulation: bool) -> None:
        control.editingFinished.connect(lambda: self._emitChange(resetSimulation))

    # :: VOID -> NONE
    # Handles a rule-family selection and publishes it
    def _ruleChanged(self) -> None:
        self._syncRuleControls()
        self._emitChange(True)

    # :: VOID -> NONE
    # Switches the contextual rule and initializer controls as one atomic edit
    def _simulationModeChanged(self) -> None:
        simulationMode = self._simulationMode.currentData()
        defaultInitial = "single_center" if simulationMode == "wolfram_2d" else "random"
        self._populateInitialTypes(simulationMode, defaultInitial)
        self._syncSimulationControls()
        self._emitChange(True)

    # :: STRING, STRING -> NONE
    # Rebuilds initializer choices for the selected simulation family
    def _populateInitialTypes(self, simulationMode: str, selectedType: str) -> None:
        self._initialType.blockSignals(True)
        self._initialType.clear()
        if simulationMode == "3d":
            choices = (
                ("Random voxels", "random"),
                ("Sphere", "sphere"),
                ("Center block", "center_block"),
                ("Explicit voxels", "cells"),
                ("Single center voxel", "single"),
                ("Orthogonal cross", "cross"),
            )
        elif simulationMode == "wolfram_2d":
            choices = (
                ("Single center cell", "single_center"),
                ("Seeded random row", "random"),
                ("Explicit centered bits", "bits"),
            )
        else:
            choices = (
                ("Random", "random"),
                ("Center block", "center_block"),
                ("Disc", "disc"),
                ("Explicit cells", "cells"),
                ("RLE pattern", "rle"),
            )
        for label, value in choices:
            self._initialType.addItem(label, value)
        selectedIndex = self._initialType.findData(selectedType)
        self._initialType.setCurrentIndex(max(0, selectedIndex))
        self._initialType.blockSignals(False)

    # :: VOID -> NONE
    # Shows controls belonging to the active simulation family
    def _syncSimulationControls(self) -> None:
        is3D = self._is3DLayer()
        wolfram = self._simulationMode.currentData() == "wolfram_2d"
        self._setFieldVisible(self._simulationForm, self._simulationMode, not is3D)
        self._setFieldVisible(self._simulationForm, self._rulePreset, not is3D and not wolfram)
        self._setFieldVisible(self._simulationForm, self._rule3D, is3D)
        self._setFieldVisible(self._simulationForm, self._wolframRule, not is3D and wolfram)
        self._setFieldVisible(self._simulationForm, self._boundary, is3D or not wolfram)
        self._syncRuleControls()
        self._syncInitialControls()

    # :: VOID -> NONE
    # Shows custom rule controls only when applicable
    def _syncRuleControls(self) -> None:
        custom = (
            not self._is3DLayer()
            and
            self._simulationMode.currentData() == "outer_totalistic"
            and self._rulePreset.currentData() == "custom"
        )
        self._setFieldVisible(self._simulationForm, self._customNotation, custom)
        self._setFieldVisible(self._simulationForm, self._neighborhood, custom)

    # :: VOID -> NONE
    # Shows either explicit grid dimensions or export-relative cell sizing
    def _syncGridControls(self) -> None:
        is3D = self._is3DLayer()
        derived = self._gridMode.currentData() == "cell_size"
        self._setFieldVisible(self._simulationForm, self._gridMode, not is3D)
        self._setFieldVisible(self._simulationForm, self._gridWidth, not is3D and not derived)
        self._setFieldVisible(self._simulationForm, self._gridHeight, not is3D and not derived)
        self._setFieldVisible(self._simulationForm, self._gridSize3D, is3D)
        self._setFieldVisible(self._simulationForm, self._cellSize, not is3D and derived)
        self._setFieldVisible(self._simulationForm, self._derivedGrid, not is3D and derived)
        if derived and not is3D:
            width, height = RESOLUTIONS[self._resolution.currentIndex()]
            cellSize = self._cellSize.value()
            gridWidth = (width + cellSize - 1) // cellSize
            gridHeight = (height + cellSize - 1) // cellSize
            self._derivedGrid.setText(f"{gridWidth} × {gridHeight} cells")

    # :: VOID -> NONE
    # Applies a grid-definition change and resets the selected simulation
    def _gridModeChanged(self) -> None:
        self._syncGridControls()
        self._emitChange(True)

    # :: VOID -> NONE
    # Recalculates the grid readout after an export-relative cell-size change
    def _cellSizeChanged(self) -> None:
        self._syncGridControls()
        self._emitChange(True)

    # :: VOID -> NONE
    # Applies an output-size change and resets simulations with derived grids
    def _resolutionChanged(self) -> None:
        self._syncGridControls()
        usesDerivedGrid = self._gridMode.currentData() == "cell_size"
        usesPixelOffset = (
            self._initialType.currentData() in {"center_block", "disc"}
            and (self._offsetX.value() != 0 or self._offsetY.value() != 0)
        )
        if self._project is not None:
            usesDerivedGrid = usesDerivedGrid or any(
                isinstance(layer, Layer2DConfig) and layer.cellSizePx is not None
                for layer in self._project.layers
            )
            usesPixelOffset = usesPixelOffset or any(
                isinstance(layer, Layer2DConfig) and layer.initial.offsetPx != (0, 0)
                for layer in self._project.layers
            )
        self._emitChange(usesDerivedGrid or usesPixelOffset)

    # :: VOID -> NONE
    # Resets geometry when a layout change alters pixel-to-cell conversion
    def _layoutChanged(self) -> None:
        usesPixelOffset = (
            self._initialType.currentData() in {"center_block", "disc"}
            and (self._offsetX.value() != 0 or self._offsetY.value() != 0)
        )
        self._emitChange(usesPixelOffset)

    # :: VOID -> NONE
    # Switches contextual projected-render controls without resetting simulation
    def _renderStyleChanged(self) -> None:
        self._syncRenderControls()
        self._emitChange(False)

    # :: VOID -> NONE
    # Applies a projection change and updates perspective-strength visibility
    def _cameraProjectionChanged(self) -> None:
        self._syncRenderControls()
        self._emitChange(False)

    # :: VOID -> NONE
    # Shows a custom seed editor only when override mode is selected
    def _syncSeedControls(self) -> None:
        custom = self._layerSeedMode.currentData() == "custom"
        self._setFieldVisible(self._generalForm, self._layerSeed, custom)

    # :: VOID -> NONE
    # Applies a seed-source change and resets the selected simulation
    def _seedModeChanged(self) -> None:
        self._syncSeedControls()
        self._updateResolvedSeed()
        self._emitChange(True)

    # :: VOID -> NONE
    # Applies a custom layer seed edit
    def _layerSeedEdited(self) -> None:
        self._updateResolvedSeed()
        self._emitChange(True)

    # :: VOID -> NONE
    # Applies a global project seed edit
    def _projectSeedEdited(self) -> None:
        self._updateResolvedSeed()
        self._emitChange(True)

    # :: VOID -> NONE
    # Displays the exact seed used by the selected layer
    def _updateResolvedSeed(self) -> None:
        if self._project is None:
            return
        try:
            projectSeed = self._seedValue(self._projectSeed, "Project seed")
            if self._layerSeedMode.currentData() == "custom":
                resolvedSeed = self._seedValue(self._layerSeed, "Layer seed")
            else:
                layerId = self._project.layers[self._layerIndex].id
                resolvedSeed = stableLayerSeed(projectSeed, layerId)
        except ValueError:
            self._resolvedSeed.setText("Invalid seed")
            return
        self._resolvedSeed.setText(str(resolvedSeed))

    # :: VOID -> NONE
    # Handles an initializer selection and publishes it
    def _initialChanged(self) -> None:
        self._syncInitialControls()
        self._emitChange(True)

    # :: VOID -> NONE
    # Shows only fields used by the selected initializer
    def _syncInitialControls(self) -> None:
        is3D = self._is3DLayer()
        initialType = self._initialType.currentData()
        self._setFieldVisible(
            self._initialForm,
            self._density,
            initialType in {"random", "center_block", "disc", "sphere"},
        )
        self._setFieldVisible(
            self._initialForm,
            self._radius,
            initialType in {"center_block", "disc", "sphere"},
        )
        self._setFieldVisible(
            self._initialForm,
            self._offsetX,
            not is3D and initialType in {"center_block", "disc"},
        )
        self._setFieldVisible(
            self._initialForm,
            self._offsetY,
            not is3D and initialType in {"center_block", "disc"},
        )
        self._setFieldVisible(self._initialForm, self._origin, initialType == "cells")
        self._setFieldVisible(self._initialForm, self._cells, initialType == "cells")
        self._setFieldVisible(self._initialForm, self._rle, initialType == "rle")
        self._setFieldVisible(self._initialForm, self._bits, initialType == "bits")

    # :: VOID -> BOOL
    # Returns whether the selected model is a three-dimensional layer
    def _is3DLayer(self) -> bool:
        return (
            self._project is not None
            and isinstance(self._project.layers[self._layerIndex], Layer3DConfig)
        )

    # :: VOID -> NONE
    # Applies all contextual visibility for the selected layer dimension
    def _syncDimensionControls(self) -> None:
        is3D = self._is3DLayer()
        self._syncSimulationControls()
        self._syncGridControls()
        self._syncInitialControls()
        self._setFieldVisible(self._appearanceForm, self._liveColor, not is3D)
        self._setFieldVisible(self._appearanceForm, self._layout, not is3D)
        self._setFieldVisible(self._appearanceForm, self._renderStyle3D, is3D)
        self._setFieldVisible(self._appearanceForm, self._palette3D, is3D)
        self._setFieldVisible(self._appearanceForm, self._voxelScale, is3D)
        self._setFieldVisible(self._appearanceForm, self._surfaceOnly, is3D)
        self._syncRenderControls()

    # :: VOID -> NONE
    # Shows projected-only appearance and camera controls contextually
    def _syncRenderControls(self) -> None:
        projected = self._is3DLayer() and self._renderStyle3D.currentData() == "projected_voxel"
        self._setFieldVisible(self._appearanceForm, self._colorBy, projected)
        self._setFieldVisible(self._appearanceForm, self._depthShading, projected)
        self._setFieldVisible(self._appearanceForm, self._vignette, projected)
        self._cameraGroup.setVisible(projected)
        showPerspective = projected and self._cameraProjection.currentData() == "perspective"
        self._perspectiveStrength.setVisible(showPerspective)
        label = self._cameraGroup.layout().labelForField(self._perspectiveStrength)
        if label is not None:
            label.setVisible(showPerspective)

    # :: formLayout, widget, BOOL -> NONE
    # Shows or hides a form field together with its label
    def _setFieldVisible(self, form: QFormLayout, field: QWidget, visible: bool) -> None:
        label = form.labelForField(field)
        if label is not None:
            label.setVisible(visible)
        field.setVisible(visible)

    # :: lineEdit, STRING -> INT
    # Parses a seed field across the full supported 63-bit range
    def _seedValue(self, control: QLineEdit, label: str) -> int:
        value = control.text().strip()
        if not value.isdigit():
            raise ValueError(f"{label} must be a non-negative integer")
        seed = int(value)
        if seed > 2**63 - 1:
            raise ValueError(f"{label} must be no greater than 9223372036854775807")
        return seed

    # :: VOID -> ARRAY<STRING, ANY>
    # Builds the selected initializer mapping
    def _initialData(self) -> dict[str, object]:
        initialType = self._initialType.currentData()
        is3D = self._is3DLayer()
        if initialType in {"single_center", "single", "cross"}:
            return {"type": initialType}
        if initialType == "bits":
            compact = "".join(self._bits.text().split())
            if not compact or any(character not in "01" for character in compact):
                raise ValueError("Wolfram bits must contain only zero and one")
            return {"type": initialType, "bits": [int(character) for character in compact]}
        if initialType == "random":
            return {"type": initialType, "density": self._density.value()}
        if initialType in {"center_block", "disc", "sphere"}:
            data: dict[str, object] = {
                "type": initialType,
                "density": self._density.value(),
                "radius": self._radius.value(),
            }
            if not is3D:
                data["offset_px"] = [self._offsetX.value(), self._offsetY.value()]
            return data
        if initialType == "cells":
            cells: list[list[int]] = []
            for lineNumber, line in enumerate(self._cells.toPlainText().splitlines(), 1):
                if not line.strip():
                    continue
                parts = [part.strip() for part in line.split(",")]
                coordinateCount = 3 if is3D else 2
                coordinateLabel = "x,y,z" if is3D else "x,y"
                if len(parts) != coordinateCount:
                    raise ValueError(f"Cell line {lineNumber} must contain {coordinateLabel}")
                try:
                    cells.append([int(part) for part in parts])
                except ValueError as error:
                    raise ValueError(f"Cell line {lineNumber} must contain integers") from error
            return {"type": initialType, "origin": self._origin.currentData(), "cells": cells}
        return {"type": "rle", "data": self._rle.toPlainText(), "origin": "center"}

    # :: BOOL -> NONE
    # Emits the current mapping unless values are still loading
    def _emitChange(self, resetSimulation: bool) -> None:
        if self._loading:
            return
        try:
            data = self.projectData()
        except ValueError as error:
            self.validationError.emit(str(error))
            return
        self.edited.emit(data, resetSimulation)

    # :: VOID -> NONE
    # Debounces multi-line cell and RLE editing
    def _queueTextChange(self) -> None:
        if not self._loading:
            self._textTimer.start()
