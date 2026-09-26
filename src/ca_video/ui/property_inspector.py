from __future__ import annotations  # Enable forward references in type annotations

from copy import deepcopy  # Build isolated editable project mappings

from PySide6.QtCore import Qt, QTimer, Signal  # Debounce text edits and publish validated changes
from PySide6.QtGui import QColor  # Convert native color selections
from PySide6.QtWidgets import (  # Build the project and layer inspector forms
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
from ca_video.config.models import ProjectConfig, colorToHex  # Present normalized project values

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
        self._projectSeed.setValue(min(project.seed, self._projectSeed.maximum()))
        resolutionIndex = self._resolution.findData((project.output.width, project.output.height))
        self._resolution.setCurrentIndex(max(0, resolutionIndex))
        fpsIndex = self._fps.findData(project.output.fps)
        self._fps.setCurrentIndex(max(0, fpsIndex))
        self._duration.setValue(project.output.durationSeconds)
        self._backgroundColor.setColor(colorToHex(project.canvasBackground))

        self._layerName.setText(layer.name)
        ruleIndex = self._rulePreset.findData(layer.rulePreset or "custom")
        self._rulePreset.setCurrentIndex(max(0, ruleIndex))
        self._customNotation.setText(layer.rule.notation)
        neighborhoodIndex = self._neighborhood.findData(layer.rule.neighborhood)
        self._neighborhood.setCurrentIndex(max(0, neighborhoodIndex))
        self._gridWidth.setValue(layer.gridWidth)
        self._gridHeight.setValue(layer.gridHeight)
        self._boundary.setCurrentIndex(max(0, self._boundary.findData(layer.boundary)))

        self._initialType.setCurrentIndex(max(0, self._initialType.findData(initial.type)))
        self._density.setValue(initial.density)
        self._radius.setValue(initial.radius)
        self._origin.setCurrentIndex(max(0, self._origin.findData(initial.origin)))
        self._cells.setPlainText("\n".join(f"{xValue},{yValue}" for xValue, yValue in initial.cells))
        rleText = initial.rleData or ""
        if not rleText and initial.rlePath is not None:
            source = initial.rlePath if initial.rlePath.is_absolute() else project.baseDir / initial.rlePath
            try:
                rleText = source.read_text(encoding="utf-8")
            except OSError:
                rleText = ""
        self._rle.setPlainText(rleText or "x = 3, y = 3\nbob$2bo$3o!")

        self._liveColor.setColor(colorToHex(layer.liveColor))
        self._opacity.setValue(layer.opacity)
        self._layout.setCurrentIndex(max(0, self._layout.findData(layer.layout)))
        self._stepInterval.setValue(layer.stepIntervalMs)
        self._syncRuleControls()
        self._syncInitialControls()
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
        projectData["seed"] = self._projectSeed.value()
        width, height = self._resolution.currentData()
        outputData["width"] = width
        outputData["height"] = height
        outputData["fps"] = self._fps.currentData()
        outputData["duration_seconds"] = self._duration.value()
        canvasData["background"] = self._backgroundColor.color

        layerData["name"] = self._layerName.text().strip()
        ruleKey = self._rulePreset.currentData()
        simulationData["rule"] = (
            {"notation": self._customNotation.text().strip(), "neighborhood": self._neighborhood.currentData()}
            if ruleKey == "custom"
            else {"preset": ruleKey}
        )
        simulationData["grid"] = {
            "size": [self._gridWidth.value(), self._gridHeight.value()],
            "boundary": self._boundary.currentData(),
        }
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
        self._layerName = QLineEdit()
        generalForm.addRow("Name", self._layerName)
        layout.addWidget(general)

        simulation = QGroupBox("Simulation")
        simulationForm = QFormLayout(simulation)
        self._simulationForm = simulationForm
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
        self._customNotation = QLineEdit("B3/S23")
        self._customNotation.setPlaceholderText("B3/S23 or B2/S/C3")
        self._neighborhood = QComboBox()
        self._neighborhood.addItem("Moore (8 neighbors)", "moore")
        self._neighborhood.addItem("von Neumann (4 neighbors)", "von_neumann")
        self._gridWidth = self._spinBox(8, 2048)
        self._gridHeight = self._spinBox(8, 2048)
        self._boundary = QComboBox()
        self._boundary.addItem("Wrap", "wrap")
        self._boundary.addItem("Fixed", "fixed")
        simulationForm.addRow("Rule", self._rulePreset)
        simulationForm.addRow("Notation", self._customNotation)
        simulationForm.addRow("Neighborhood", self._neighborhood)
        simulationForm.addRow("Grid width", self._gridWidth)
        simulationForm.addRow("Grid height", self._gridHeight)
        simulationForm.addRow("Boundary", self._boundary)
        layout.addWidget(simulation)

        initial = QGroupBox("Initial Condition")
        initialForm = QFormLayout(initial)
        self._initialForm = initialForm
        self._initialType = QComboBox()
        self._initialType.addItem("Random", "random")
        self._initialType.addItem("Center block", "center_block")
        self._initialType.addItem("Disc", "disc")
        self._initialType.addItem("Explicit cells", "cells")
        self._initialType.addItem("RLE pattern", "rle")
        self._density = QDoubleSpinBox()
        self._density.setRange(0, 1)
        self._density.setSingleStep(0.05)
        self._density.setDecimals(2)
        self._radius = self._spinBox(1, 2048)
        self._origin = QComboBox()
        self._origin.addItem("Centered", "center")
        self._origin.addItem("Absolute", "absolute")
        self._cells = QPlainTextEdit()
        self._cells.setPlaceholderText("One x,y coordinate per line")
        self._cells.setMaximumHeight(90)
        self._rle = QPlainTextEdit()
        self._rle.setPlaceholderText("Paste a two-state Life RLE pattern")
        self._rle.setMaximumHeight(110)
        initialForm.addRow("Type", self._initialType)
        initialForm.addRow("Density", self._density)
        initialForm.addRow("Radius", self._radius)
        initialForm.addRow("Coordinates", self._origin)
        initialForm.addRow("Cells", self._cells)
        initialForm.addRow("RLE", self._rle)
        layout.addWidget(initial)

        appearance = QGroupBox("Appearance")
        appearanceForm = QFormLayout(appearance)
        self._liveColor = ColorButton("#e8f4ff")
        self._opacity = QDoubleSpinBox()
        self._opacity.setRange(0, 1)
        self._opacity.setSingleStep(0.05)
        self._opacity.setDecimals(2)
        self._layout = QComboBox()
        self._layout.addItem("Fit", "fit")
        self._layout.addItem("Cover", "cover")
        appearanceForm.addRow("Live color", self._liveColor)
        appearanceForm.addRow("Opacity", self._opacity)
        appearanceForm.addRow("Layout", self._layout)
        layout.addWidget(appearance)

        timing = QGroupBox("Timing")
        timingForm = QFormLayout(timing)
        self._stepInterval = self._spinBox(1, 60_000, " ms")
        timingForm.addRow("Step interval", self._stepInterval)
        layout.addWidget(timing)
        layout.addStretch(1)

        self._rulePreset.currentIndexChanged.connect(self._ruleChanged)
        self._initialType.currentIndexChanged.connect(self._initialChanged)
        self._connectLineEdit(self._layerName, True)
        self._connectLineEdit(self._customNotation, True)
        for control in (
            self._neighborhood,
            self._gridWidth,
            self._gridHeight,
            self._boundary,
            self._density,
            self._radius,
            self._origin,
            self._stepInterval,
        ):
            control.currentIndexChanged.connect(lambda _value: self._emitChange(True)) if isinstance(
                control, QComboBox
            ) else control.valueChanged.connect(lambda _value: self._emitChange(True))
        self._cells.textChanged.connect(self._queueTextChange)
        self._rle.textChanged.connect(self._queueTextChange)
        self._liveColor.colorChanged.connect(lambda _value: self._emitChange(False))
        self._opacity.valueChanged.connect(lambda _value: self._emitChange(False))
        self._layout.currentIndexChanged.connect(lambda _value: self._emitChange(False))
        return container

    # :: VOID -> widget
    # Builds project and output settings
    def _buildProjectTab(self) -> QWidget:
        container, content, layout = self._scrollingTab()

        projectGroup = QGroupBox("Project")
        projectForm = QFormLayout(projectGroup)
        self._projectName = QLineEdit()
        self._projectSeed = self._spinBox(0, 2_147_483_647)
        projectForm.addRow("Name", self._projectName)
        projectForm.addRow("Random seed", self._projectSeed)
        layout.addWidget(projectGroup)

        outputGroup = QGroupBox("Output")
        outputForm = QFormLayout(outputGroup)
        self._resolution = QComboBox()
        for width, height in RESOLUTIONS:
            self._resolution.addItem(f"{width} × {height}", (width, height))
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
        self._projectSeed.valueChanged.connect(lambda _value: self._emitChange(True))
        self._resolution.currentIndexChanged.connect(lambda _value: self._emitChange(False))
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
    # Shows custom rule controls only when applicable
    def _syncRuleControls(self) -> None:
        custom = self._rulePreset.currentData() == "custom"
        self._setFieldVisible(self._simulationForm, self._customNotation, custom)
        self._setFieldVisible(self._simulationForm, self._neighborhood, custom)

    # :: VOID -> NONE
    # Handles an initializer selection and publishes it
    def _initialChanged(self) -> None:
        self._syncInitialControls()
        self._emitChange(True)

    # :: VOID -> NONE
    # Shows only fields used by the selected initializer
    def _syncInitialControls(self) -> None:
        initialType = self._initialType.currentData()
        self._setFieldVisible(
            self._initialForm,
            self._density,
            initialType in {"random", "center_block", "disc"},
        )
        self._setFieldVisible(self._initialForm, self._radius, initialType in {"center_block", "disc"})
        self._setFieldVisible(self._initialForm, self._origin, initialType == "cells")
        self._setFieldVisible(self._initialForm, self._cells, initialType == "cells")
        self._setFieldVisible(self._initialForm, self._rle, initialType == "rle")

    # :: formLayout, widget, BOOL -> NONE
    # Shows or hides a form field together with its label
    def _setFieldVisible(self, form: QFormLayout, field: QWidget, visible: bool) -> None:
        label = form.labelForField(field)
        if label is not None:
            label.setVisible(visible)
        field.setVisible(visible)

    # :: VOID -> ARRAY<STRING, ANY>
    # Builds the selected initializer mapping
    def _initialData(self) -> dict[str, object]:
        initialType = self._initialType.currentData()
        if initialType == "random":
            return {"type": initialType, "density": self._density.value()}
        if initialType in {"center_block", "disc"}:
            return {"type": initialType, "density": self._density.value(), "radius": self._radius.value()}
        if initialType == "cells":
            cells: list[list[int]] = []
            for lineNumber, line in enumerate(self._cells.toPlainText().splitlines(), 1):
                if not line.strip():
                    continue
                parts = [part.strip() for part in line.split(",")]
                if len(parts) != 2:
                    raise ValueError(f"Cell line {lineNumber} must contain x,y")
                try:
                    cells.append([int(parts[0]), int(parts[1])])
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
