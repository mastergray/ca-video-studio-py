import os  # Select Qt's offscreen integration backend before importing Qt

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # Create the Qt test event loop  # noqa: E402

from ca_video.config.models import defaultProject  # Create a preview project  # noqa: E402
from ca_video.ui.main_window import MainWindow  # Exercise the native window  # noqa: E402


def test_main_window_displays_initial_frame() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow(defaultProject())
    window.show()
    app.processEvents()
    assert window.preview.pixmap() is not None
    assert window.runtime.engine.generation == 0
    window.close()


def test_preview_transport_uses_shared_runtime() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow(defaultProject())
    for _ in range(3):
        window._advancePreview()
    app.processEvents()
    assert window.frameIndex == 3
    assert window.runtime.engine.generation == 1
    window._resetPreview()
    assert window.frameIndex == 0
    assert window.runtime.engine.generation == 0
    window.close()


def test_fade_rate_is_a_visual_edit_that_preserves_simulation_state() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow(defaultProject())
    for _ in range(3):
        window._advancePreview()
    generation = window.runtime.engine.generation

    window.inspector._fadeRate.setValue(6.5)
    app.processEvents()

    assert window.project.layer.fadeRate == 6.5
    assert window.runtime.engine.generation == generation
    assert window.inspector._fadeRate.isVisibleTo(window.inspector)
    window._setDirty(False)
    window.close()


def test_editor_changes_custom_rule_and_saves_project(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow(defaultProject(tmp_path))
    inspector = window.inspector
    customIndex = inspector._rulePreset.findData("custom")
    inspector._rulePreset.setCurrentIndex(customIndex)
    inspector._customNotation.setText("B2/S/C3")
    inspector._customNotation.editingFinished.emit()
    inspector._projectName.setText("Edited Brain")
    inspector._projectName.editingFinished.emit()
    app.processEvents()

    assert window.project.layer.rule.notation == "B2/S/C3"
    assert window.project.name == "Edited Brain"
    assert window.dirty

    destination = tmp_path / "edited.cav.json"
    window._projectPath = destination
    assert window._saveProject()
    assert destination.exists()
    assert not window.dirty
    window.close()


def test_preview_only_mode_restores_editor_panes() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow(defaultProject())
    window.show()
    window._previewOnlyAction.setChecked(True)
    window._togglePreviewOnly()
    app.processEvents()
    assert not window._layerPanel.isVisible()
    assert not window.inspector.isVisible()

    window._exitPresentation()
    app.processEvents()
    assert window._layerPanel.isVisible()
    assert window.inspector.isVisible()
    window.close()


def test_layer_controls_add_duplicate_reorder_and_delete() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow(defaultProject())

    window._addLayer()
    assert len(window.project.layers) == 2
    assert len({layer.id for layer in window.project.layers}) == 2
    assert window.project.layers[0].zIndex > window.project.layers[1].zIndex

    window._duplicateLayer()
    assert len(window.project.layers) == 3
    window._moveLayer(1)
    assert window._selectedLayerIndex == 1
    assert window.project.layers[0].zIndex > window.project.layers[1].zIndex

    window._deleteLayer()
    app.processEvents()
    assert len(window.project.layers) == 2
    window._setDirty(False)
    window.close()


def test_layer_seed_can_switch_from_derived_to_custom() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow(defaultProject())
    inspector = window.inspector

    inspector._layerSeedMode.setCurrentIndex(inspector._layerSeedMode.findData("custom"))
    inspector._layerSeed.setText("424242")
    inspector._layerSeed.editingFinished.emit()
    app.processEvents()

    assert window.project.layer.seed == 424242
    assert inspector._resolvedSeed.text() == "424242"
    window._setDirty(False)
    window.close()


def test_preview_resolution_and_clock_are_independent_of_export() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow(defaultProject())
    inspector = window.inspector

    inspector._resolution.setCurrentIndex(inspector._resolution.findData("1920x1080"))
    inspector._fps.setCurrentIndex(inspector._fps.findData(60))
    app.processEvents()

    assert window.project.output.width == 1920
    assert window.project.output.fps == 60
    assert window.runtime.renderSize == (640, 360)
    assert window._timer.interval() == 33

    for _ in range(3):
        window._advancePreview()
    assert window.frameIndex == 6
    assert window.runtime.engine.generation == 1
    assert "Preview 640×360 @ 30" in window._formatLabel.text()
    assert "Export 1920×1080 @ 60" in window._formatLabel.text()
    window._setDirty(False)
    window.close()


def test_cell_size_grid_tracks_export_resolution() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow(defaultProject())
    inspector = window.inspector

    inspector._gridMode.setCurrentIndex(inspector._gridMode.findData("cell_size"))
    inspector._cellSize.setValue(8)
    inspector._resolution.setCurrentIndex(inspector._resolution.findData("1920x1080"))
    app.processEvents()

    assert window.project.layer.cellSizePx == 8
    assert window.project.layer.gridWidth == 240
    assert window.project.layer.gridHeight == 135
    assert inspector._derivedGrid.text() == "240 × 135 cells"
    assert window.runtime.renderSize == (640, 360)
    window._setDirty(False)
    window.close()


def test_add_and_edit_wolfram_layer() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow(defaultProject())

    window._addWolframLayer()
    inspector = window.inspector
    inspector._wolframRule.setValue(110)
    inspector._initialType.setCurrentIndex(inspector._initialType.findData("bits"))
    inspector._bits.setText("1011")
    inspector._bits.editingFinished.emit()
    app.processEvents()

    layer = window.project.layer
    assert len(window.project.layers) == 2
    assert layer.simulationMode == "wolfram_2d"
    assert layer.wolframRule == 110
    assert layer.initial.bits == (1, 0, 1, 1)
    assert window._layerList.item(0).text().endswith("W110")
    assert "W110" in window._infoLabel.text()
    assert inspector._wolframRule.isVisibleTo(inspector)
    assert not inspector._rulePreset.isVisibleTo(inspector)
    window._setDirty(False)
    window.close()


def test_existing_layer_can_switch_simulation_family() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow(defaultProject())
    inspector = window.inspector

    inspector._simulationMode.setCurrentIndex(inspector._simulationMode.findData("wolfram_2d"))
    app.processEvents()
    assert window.project.layer.simulationMode == "wolfram_2d"
    assert window.project.layer.wolframRule == 30
    assert window.project.layer.initial.type == "single_center"
    assert window.project.layer.boundary == "wrap"

    inspector._simulationMode.setCurrentIndex(inspector._simulationMode.findData("outer_totalistic"))
    app.processEvents()
    assert window.project.layer.simulationMode == "outer_totalistic"
    assert window.project.layer.rulePreset == "life"
    assert window.project.layer.initial.type == "random"
    window._setDirty(False)
    window.close()


def test_disc_offset_is_edited_in_export_pixels() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow(defaultProject())
    inspector = window.inspector

    inspector._initialType.setCurrentIndex(inspector._initialType.findData("disc"))
    inspector._offsetX.setValue(80)
    inspector._offsetY.setValue(-40)
    app.processEvents()

    assert window.project.layer.initial.offsetPx == (80, -40)
    assert window.runtime._shapeOffsetCells(window.project.layer) == (20, -10)
    assert inspector._offsetX.isVisibleTo(inspector)
    assert inspector._offsetY.isVisibleTo(inspector)

    for _ in range(3):
        window._advancePreview()
    assert window.runtime.engine.generation == 1
    inspector._resolution.setCurrentIndex(inspector._resolution.findData("960x540"))
    app.processEvents()
    assert window.runtime.engine.generation == 0
    assert window.runtime._shapeOffsetCells(window.project.layer) == (13, -7)
    window._setDirty(False)
    window.close()


def test_add_and_edit_3d_layer() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow(defaultProject())

    window._add3DLayer()
    inspector = window.inspector
    inspector._rule3D.setCurrentIndex(inspector._rule3D.findData("crystal"))
    inspector._gridSize3D.setValue(20)
    inspector._initialType.setCurrentIndex(inspector._initialType.findData("cross"))
    inspector._offsetX3D.setValue(3)
    inspector._offsetY3D.setValue(-2)
    inspector._offsetZ3D.setValue(1)
    inspector._fadeRate.setValue(6.5)
    inspector._palette3D.setCurrentIndex(inspector._palette3D.findData("crystal"))
    app.processEvents()

    layer = window.project.layer
    assert layer.dimension == "3d"
    assert layer.rulePreset == "crystal"
    assert layer.gridSize == 20
    assert layer.initial.type == "cross"
    assert layer.initial.offsetCells == (3, -2, 1)
    assert layer.fadeRate == 6.5
    assert window.runtime.engine.grid[11, 8, 13] == 1
    assert window._layerList.item(0).text().endswith("3D")
    assert "20³" in window._infoLabel.text()
    assert inspector._rule3D.isVisibleTo(inspector)
    assert inspector._offsetX3D.isVisibleTo(inspector)
    assert inspector._offsetY3D.isVisibleTo(inspector)
    assert inspector._offsetZ3D.isVisibleTo(inspector)
    assert inspector._fadeRate.isVisibleTo(inspector)
    assert not inspector._simulationMode.isVisibleTo(inspector)
    window._setDirty(False)
    window.close()


def test_switch_3d_layer_to_projected_camera_controls() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow(defaultProject())
    window._add3DLayer()
    inspector = window.inspector

    inspector._renderStyle3D.setCurrentIndex(
        inspector._renderStyle3D.findData("projected_voxel")
    )
    inspector._colorBy.setCurrentIndex(inspector._colorBy.findData("height"))
    inspector._cameraProjection.setCurrentIndex(
        inspector._cameraProjection.findData("orthographic")
    )
    inspector._azimuth.setValue(55)
    inspector._elevation.setValue(18)
    inspector._rotationRate.setValue(-30)
    inspector._panX.setValue(0.15)
    app.processEvents()

    layer = window.project.layer
    assert layer.renderStyle == "projected_voxel"
    assert layer.colorBy == "height"
    assert layer.camera.projection == "orthographic"
    assert layer.camera.azimuthDeg == 55
    assert layer.camera.elevationDeg == 18
    assert layer.camera.rotationDegPerSecond == -30
    assert layer.camera.panX == 0.15
    assert inspector._cameraGroup.isVisibleTo(inspector)
    assert not inspector._perspectiveStrength.isVisibleTo(inspector)
    window._setDirty(False)
    window.close()


def test_add_and_edit_wolfram_3d_layer() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow(defaultProject())

    window._addWolfram3DLayer()
    inspector = window.inspector
    inspector._wolframRule.setValue(122)
    inspector._extrusionDepth.setValue(5)
    inspector._extrusionOffset.setValue(-3)
    inspector._initialType.setCurrentIndex(inspector._initialType.findData("bits"))
    inspector._bits.setText("10110")
    inspector._bits.editingFinished.emit()
    app.processEvents()

    layer = window.project.layer
    assert layer.simulationMode == "wolfram_3d_extruded"
    assert layer.wolframRule == 122
    assert layer.extrusionDepth == 5
    assert layer.extrusionOffset == -3
    assert window.runtime.engine.extrusionOffset == -3
    assert layer.initial.bits == (1, 0, 1, 1, 0)
    assert layer.palette == "wolfram3d"
    assert window._layerList.item(0).text().endswith("W3D")
    assert "W122" in window._infoLabel.text()
    assert inspector._wolframRule.isVisibleTo(inspector)
    assert inspector._extrusionDepth.isVisibleTo(inspector)
    assert inspector._extrusionOffset.isVisibleTo(inspector)
    assert not inspector._rule3D.isVisibleTo(inspector)
    assert not inspector._boundary.isVisibleTo(inspector)
    window._setDirty(False)
    window.close()
