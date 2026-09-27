from __future__ import annotations  # Enable forward references in type annotations

import numpy as np  # Create and transform RGB frame buffers
from numpy.typing import NDArray  # Describe NumPy array types

RGBFrame = NDArray[np.uint8]
RGBAFrame = NDArray[np.float32]


# :: INT, INT, INT, INT, STRING -> (INT, INT)
# Calculates the exact intermediate grid raster used by fit or cover rendering
def scaledGridSize(
    canvasWidth: int,
    canvasHeight: int,
    gridWidth: int,
    gridHeight: int,
    layout: str,
) -> tuple[int, int]:
    scale = (
        max(canvasWidth / gridWidth, canvasHeight / gridHeight)
        if layout == "cover"
        else min(canvasWidth / gridWidth, canvasHeight / gridHeight)
    )
    return max(1, int(round(gridWidth * scale))), max(1, int(round(gridHeight * scale)))


# Converts a two-dimensional cell grid into an exact-size RGB frame
class Renderer2D:

    # CONSTRUCTOR :: INT, INT, (INT, INT, INT), (INT, INT, INT), FLOAT, STRING, INT, (INT, INT, INT) -> renderer2D
    # Creates a nearest-neighbor 2D renderer
    def __init__(
        self,
        width: int,
        height: int,
        background: tuple[int, int, int],
        liveColor: tuple[int, int, int],
        opacity: float = 1.0,
        layout: str = "fit",
        states: int = 2,
        trailColor: tuple[int, int, int] = (35, 58, 107),
    ) -> None:
        self._width = width
        self._height = height
        self._background = np.asarray(background, dtype=np.float32)
        self._liveColor = np.asarray(liveColor, dtype=np.float32)
        self._opacity = opacity
        self._layout = layout
        self._states = states
        self._trailColor = np.asarray(trailColor, dtype=np.float32)

    #
    # Instance Methods
    #

    # :: grid -> rgbFrame
    # Renders the supplied cell grid to an RGB frame
    def render(self, grid: NDArray[np.uint8]) -> RGBFrame:
        layer = self.renderLayer(grid)
        alpha = layer[..., 3:4]
        frame = self._background * (1.0 - alpha) + layer[..., :3] * alpha
        return frame.clip(0, 255).astype(np.uint8)

    # :: grid, FLOAT, presence?, grid?, trailBuffer? -> rgbaFrame
    # Renders transparent color and alpha for project composition
    def renderLayer(
        self,
        grid: NDArray[np.uint8],
        presentationSeconds: float = 0,
        presence: NDArray[np.float32] | None = None,
        displayGrid: NDArray[np.uint8] | None = None,
        trailValues: NDArray[np.float32] | None = None,
    ) -> RGBAFrame:
        gridHeight, gridWidth = grid.shape
        renderWidth, renderHeight = scaledGridSize(
            self._width,
            self._height,
            gridWidth,
            gridHeight,
            self._layout,
        )
        visualGrid = displayGrid if displayGrid is not None else grid
        resized = self._resizeNearest(visualGrid, renderWidth, renderHeight)

        intensity = np.zeros(resized.shape, dtype=np.float32)
        intensity[resized == 1] = 1.0
        if self._states > 2:
            decaying = resized >= 2
            intensity[decaying] = (self._states - resized[decaying]) / (self._states - 1)
        if presence is not None:
            intensity *= self._resizeNearest(presence, renderWidth, renderHeight)
        trailPresence = np.zeros_like(intensity)
        if trailValues is not None:
            currentGrid = self._resizeNearest(grid, renderWidth, renderHeight)
            resizedTrail = self._resizeNearest(trailValues, renderWidth, renderHeight)
            trailPresence[currentGrid == 0] = resizedTrail[currentGrid == 0]
        combinedPresence = intensity + trailPresence * (1 - intensity)
        premultiplied = (
            self._liveColor * intensity[..., None]
            + self._trailColor * (trailPresence * (1 - intensity))[..., None]
        )
        layer = np.empty((renderHeight, renderWidth, 4), dtype=np.float32)
        layer[..., :3] = self._liveColor
        visible = combinedPresence > 0
        layer[visible, :3] = premultiplied[visible] / combinedPresence[visible, None]
        layer[..., 3] = combinedPresence * self._opacity

        if self._layout == "cover":
            offsetX = max(0, (renderWidth - self._width) // 2)
            offsetY = max(0, (renderHeight - self._height) // 2)
            return layer[
                offsetY : offsetY + self._height,
                offsetX : offsetX + self._width,
            ]

        frame = np.zeros((self._height, self._width, 4), dtype=np.float32)
        offsetX = (self._width - renderWidth) // 2
        offsetY = (self._height - renderHeight) // 2
        frame[offsetY : offsetY + renderHeight, offsetX : offsetX + renderWidth] = layer
        return frame

    #
    # Protected Methods
    #

    # :: grid, INT, INT -> grid
    # Resizes a grid using deterministic nearest-neighbor sampling
    def _resizeNearest(
        self,
        grid: NDArray[np.uint8] | NDArray[np.float32],
        width: int,
        height: int,
    ) -> NDArray[np.uint8] | NDArray[np.float32]:
        sourceHeight, sourceWidth = grid.shape
        xIndices = np.minimum((np.arange(width) * sourceWidth // width), sourceWidth - 1)
        yIndices = np.minimum((np.arange(height) * sourceHeight // height), sourceHeight - 1)
        return grid[yIndices[:, None], xIndices[None, :]]
