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
