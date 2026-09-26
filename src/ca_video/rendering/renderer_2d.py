from __future__ import annotations  # Enable forward references in type annotations

import numpy as np  # Create and transform RGB frame buffers
from numpy.typing import NDArray  # Describe NumPy array types

RGBFrame = NDArray[np.uint8]


# Converts a two-dimensional cell grid into an exact-size RGB frame
class Renderer2D:

    # CONSTRUCTOR :: INT, INT, (INT, INT, INT), (INT, INT, INT), FLOAT, STRING -> renderer2D
    # Creates a nearest-neighbor 2D renderer
    def __init__(
        self,
        width: int,
        height: int,
        background: tuple[int, int, int],
        liveColor: tuple[int, int, int],
        opacity: float = 1.0,
        layout: str = "fit",
    ) -> None:
        self._width = width
        self._height = height
        self._background = np.asarray(background, dtype=np.float32)
        self._liveColor = np.asarray(liveColor, dtype=np.float32)
        self._opacity = opacity
        self._layout = layout

    #
    # Instance Methods
    #

    # :: grid -> rgbFrame
    # Renders the supplied cell grid to an RGB frame
    def render(self, grid: NDArray[np.uint8]) -> RGBFrame:
        gridHeight, gridWidth = grid.shape
        if self._layout == "cover":
            scale = max(self._width / gridWidth, self._height / gridHeight)
        else:
            scale = min(self._width / gridWidth, self._height / gridHeight)
        renderWidth = max(1, int(round(gridWidth * scale)))
        renderHeight = max(1, int(round(gridHeight * scale)))
        mask = self._resizeNearest(grid, renderWidth, renderHeight).astype(bool)

        layer = np.empty((renderHeight, renderWidth, 3), dtype=np.float32)
        layer[:] = self._background
        blendedLive = self._background * (1.0 - self._opacity) + self._liveColor * self._opacity
        layer[mask] = blendedLive

        if self._layout == "cover":
            offsetX = max(0, (renderWidth - self._width) // 2)
            offsetY = max(0, (renderHeight - self._height) // 2)
            return layer[
                offsetY : offsetY + self._height,
                offsetX : offsetX + self._width,
            ].clip(0, 255).astype(np.uint8)

        frame = np.empty((self._height, self._width, 3), dtype=np.float32)
        frame[:] = self._background
        offsetX = (self._width - renderWidth) // 2
        offsetY = (self._height - renderHeight) // 2
        frame[offsetY : offsetY + renderHeight, offsetX : offsetX + renderWidth] = layer
        return frame.clip(0, 255).astype(np.uint8)

    #
    # Protected Methods
    #

    # :: grid, INT, INT -> grid
    # Resizes a grid using deterministic nearest-neighbor sampling
    def _resizeNearest(
        self,
        grid: NDArray[np.uint8],
        width: int,
        height: int,
    ) -> NDArray[np.uint8]:
        sourceHeight, sourceWidth = grid.shape
        xIndices = np.minimum((np.arange(width) * sourceWidth // width), sourceWidth - 1)
        yIndices = np.minimum((np.arange(height) * sourceHeight // height), sourceHeight - 1)
        return grid[yIndices[:, None], xIndices[None, :]]
