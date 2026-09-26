from __future__ import annotations  # Enable forward references in type annotations

import numpy as np  # Extract visible voxels and expose RGBA buffers
from numpy.typing import NDArray  # Describe voxel grids and rendered layers
from PySide6.QtCore import QPointF, Qt  # Build isometric face polygons
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPolygonF  # Rasterize voxels offscreen

from ca_video.catalogs.rules_3d import Palette3D  # Color voxel faces

RGBAFrame = NDArray[np.float32]


# Rasterizes cubic automata as depth-ordered isometric voxels
class Renderer3D:

    # CONSTRUCTOR :: INT, INT, palette3D, FLOAT, INT, BOOL, STRING -> renderer3D
    # Creates an isometric surface renderer
    def __init__(
        self,
        width: int,
        height: int,
        palette: Palette3D,
        opacity: float = 1,
        voxelScale: int = 0,
        surfaceOnly: bool = True,
        boundary: str = "fixed",
    ) -> None:
        self._width = width
        self._height = height
        self._palette = palette
        self._opacity = opacity
        self._voxelScale = voxelScale
        self._surfaceOnly = surfaceOnly
        self._boundary = boundary

    #
    # Instance Methods
    #

    # :: grid3D -> rgbaFrame
    # Renders occupied voxels into a transparent layer
    def renderLayer(self, grid: NDArray[np.uint8]) -> RGBAFrame:
        if grid.ndim != 3 or len(set(grid.shape)) != 1:
            raise ValueError("3D renderer requires a cubic voxel grid")
        image = QImage(self._width, self._height, QImage.Format.Format_RGBA8888)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        gridSize = grid.shape[0]
        tileWidth = self._voxelScale or max(2, int(min(self._width, self._height) * 0.45 / gridSize))
        tileHeight = max(1, tileWidth // 2)
        originX = self._width / 2
        originY = self._height / 2
        coordinates = self._visibleCoordinates(grid)
        maximumZ = max(gridSize - 1, 1)
        colorsByZ: dict[int, tuple[QColor, QColor, QColor, QColor]] = {}

        for zValue, yValue, xValue in coordinates:
            zIndex, yIndex, xIndex = int(zValue), int(yValue), int(xValue)
            if zIndex not in colorsByZ:
                brightness = 0.35 + 0.65 * zIndex / maximumZ
                colorsByZ[zIndex] = (
                    self._shade(self._palette.top, brightness),
                    self._shade(self._palette.left, brightness),
                    self._shade(self._palette.right, brightness),
                    self._shade(self._palette.outline, 0.7),
                )
            top, left, right, outline = colorsByZ[zIndex]
            screenX = originX + (xIndex - yIndex) * tileWidth
            screenY = originY + (xIndex + yIndex - 2 * zIndex) * tileHeight
            self._drawVoxel(painter, screenX, screenY, tileWidth, tileHeight, top, left, right, outline)

        painter.end()
        bytesPerLine = image.bytesPerLine()
        buffer = np.frombuffer(image.bits(), dtype=np.uint8, count=image.sizeInBytes())
        rgba = buffer.reshape(self._height, bytesPerLine)[:, : self._width * 4]
        layer = rgba.reshape(self._height, self._width, 4).astype(np.float32, copy=True)
        layer[..., 3] *= self._opacity / 255
        return layer

    #
    # Protected Methods
    #

    # :: grid3D -> array
    # Extracts occupied or surface coordinates in painter depth order
    def _visibleCoordinates(self, grid: NDArray[np.uint8]) -> NDArray[np.int64]:
        occupied = grid > 0
        visible = occupied
        if self._surfaceOnly:
            neighbors = self._orthogonalOccupancy(occupied)
            visible = occupied & (neighbors < 6)
        coordinates = np.argwhere(visible)
        if not len(coordinates):
            return coordinates
        depth = coordinates.sum(axis=1)
        order = np.lexsort((coordinates[:, 2], coordinates[:, 1], coordinates[:, 0], depth))
        return coordinates[order]

    # :: array -> array
    # Counts occupied orthogonal neighbors with the configured boundary
    def _orthogonalOccupancy(self, occupied: NDArray[np.bool_]) -> NDArray[np.uint8]:
        offsets = ((-1, 0, 0), (1, 0, 0), (0, -1, 0), (0, 1, 0), (0, 0, -1), (0, 0, 1))
        counts = np.zeros(occupied.shape, dtype=np.uint8)
        if self._boundary == "wrap":
            for offset in offsets:
                counts += np.roll(occupied, offset, axis=(0, 1, 2))
            return counts
        padded = np.pad(occupied, 1, mode="constant")
        gridSize = occupied.shape[0]
        for deltaZ, deltaY, deltaX in offsets:
            startZ, startY, startX = deltaZ + 1, deltaY + 1, deltaX + 1
            counts += padded[
                startZ : startZ + gridSize,
                startY : startY + gridSize,
                startX : startX + gridSize,
            ]
        return counts

    # :: qPainter, FLOAT, FLOAT, INT, INT, qColor, qColor, qColor, qColor -> NONE
    # Draws the top, left, and right faces of one voxel
    def _drawVoxel(
        self,
        painter: QPainter,
        screenX: float,
        screenY: float,
        width: int,
        height: int,
        top: QColor,
        left: QColor,
        right: QColor,
        outline: QColor,
    ) -> None:
        painter.setPen(QPen(outline, 1))
        faces = (
            (
                top,
                ((screenX, screenY - height), (screenX + width, screenY), (screenX, screenY + height), (screenX - width, screenY)),
            ),
            (
                left,
                ((screenX - width, screenY), (screenX, screenY + height), (screenX, screenY + height * 3), (screenX - width, screenY + height * 2)),
            ),
            (
                right,
                ((screenX + width, screenY), (screenX, screenY + height), (screenX, screenY + height * 3), (screenX + width, screenY + height * 2)),
            ),
        )
        for color, points in faces:
            painter.setBrush(color)
            painter.drawPolygon(QPolygonF([QPointF(xValue, yValue) for xValue, yValue in points]))

    # :: (INT, INT, INT), FLOAT -> qColor
    # Applies depth brightness to a face color
    def _shade(self, color: tuple[int, int, int], brightness: float) -> QColor:
        return QColor(*(min(255, int(channel * brightness)) for channel in color))
