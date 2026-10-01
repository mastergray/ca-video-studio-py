from __future__ import annotations  # Enable forward references in type annotations

import numpy as np  # Validate and expose RGB preview buffers
from PySide6.QtCore import Qt  # Configure widget alignment and scaling
from PySide6.QtGui import QImage, QPixmap, QResizeEvent  # Bridge arrays into Qt images
from PySide6.QtWidgets import QLabel, QSizePolicy  # Build the preview widget


# Displays owned RGB frames while preserving their aspect ratio
class PreviewWidget(QLabel):

    # CONSTRUCTOR :: VOID -> previewWidget
    # Creates an expandable 16:9-oriented preview surface
    def __init__(self) -> None:
        super().__init__()
        self._image: QImage | None = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(480, 270)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background: #080a0e; border: 1px solid #30363d;")

    #
    # Instance Methods
    #

    # :: ndarray -> NONE
    # Copies an RGB NumPy frame into Qt-owned memory and displays it
    def setFrame(self, frame: np.ndarray) -> None:
        if frame.ndim != 3 or frame.shape[2] != 3 or frame.dtype != np.uint8:
            raise ValueError("preview frame must be an HxWx3 uint8 array")
        height, width, _ = frame.shape
        image = QImage(
            frame.data,
            width,
            height,
            int(frame.strides[0]),
            QImage.Format.Format_RGB888,
        )
        self._image = image.copy()
        self._updatePixmap()

    # :: qResizeEvent -> NONE
    # Refreshes the scaled preview after Qt resizes the widget
    # NOTE: The name is fixed by the Qt override contract
    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._updatePixmap()

    #
    # Protected Methods
    #

    # :: VOID -> NONE
    # Scales the current image into the available widget area
    def _updatePixmap(self) -> None:
        if self._image is None:
            return
        pixmap = QPixmap.fromImage(self._image).scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        self.setPixmap(pixmap)
