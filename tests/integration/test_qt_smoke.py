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
