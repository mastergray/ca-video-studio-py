from __future__ import annotations  # Enable forward references in type annotations

import numpy as np  # Construct deterministic voxel grids
from numpy.typing import NDArray  # Describe NumPy voxel grids

Grid3D = NDArray[np.uint8]


# :: INT, STRING, FLOAT, INT, INT, ((INT, INT, INT)), STRING, STRING, (INT, INT, INT) -> grid3D
# Creates a cubic voxel grid from a validated initialization description
def initializeGrid3D(
    gridSize: int,
    initialType: str,
    density: float,
    radius: int,
    seed: int,
    cells: tuple[tuple[int, int, int], ...] = (),
    origin: str = "center",
    boundary: str = "fixed",
    offsetCells: tuple[int, int, int] = (0, 0, 0),
) -> Grid3D:
    if initialType == "random":
        randomGenerator = np.random.default_rng(seed)
        return (randomGenerator.random((gridSize, gridSize, gridSize)) < density).astype(np.uint8)
    if initialType == "single":
        grid = np.zeros((gridSize, gridSize, gridSize), dtype=np.uint8)
        _placeVoxels(grid, ((0, 0, 0),), offsetCells, boundary)
        return grid
    if initialType == "cross":
        grid = np.zeros((gridSize, gridSize, gridSize), dtype=np.uint8)
        cross = (
            (0, 0, 0),
            (-1, 0, 0),
            (1, 0, 0),
            (0, -1, 0),
            (0, 1, 0),
            (0, 0, -1),
            (0, 0, 1),
        )
        _placeVoxels(grid, cross, offsetCells, boundary)
        return grid
    if initialType in {"sphere", "center_block"}:
        axis = np.arange(-radius, radius + 1)
        if initialType == "sphere":
            mask = (
                axis[:, None, None] ** 2
                + axis[None, :, None] ** 2
                + axis[None, None, :] ** 2
                <= radius**2
            )
        else:
            mask = np.ones((len(axis), len(axis), len(axis)), dtype=bool)
        randomGenerator = np.random.default_rng(seed)
        filled = mask & (randomGenerator.random(mask.shape) < density)
        grid = np.zeros((gridSize, gridSize, gridSize), dtype=np.uint8)
        coordinates = tuple(
            (int(xIndex - radius), int(yIndex - radius), int(zIndex - radius))
            for zIndex, yIndex, xIndex in np.argwhere(filled)
        )
        shapeCenter = (gridSize - len(axis)) // 2 + radius
        _placeVoxels(grid, coordinates, offsetCells, boundary, shapeCenter)
        return grid
    if initialType == "cells":
        grid = np.zeros((gridSize, gridSize, gridSize), dtype=np.uint8)
        offset = gridSize // 2 if origin == "center" else 0
        for xValue, yValue, zValue in cells:
            xIndex, yIndex, zIndex = xValue + offset, yValue + offset, zValue + offset
            if boundary == "wrap":
                xIndex %= gridSize
                yIndex %= gridSize
                zIndex %= gridSize
            elif not all(0 <= value < gridSize for value in (xIndex, yIndex, zIndex)):
                raise ValueError(f"voxel [{xValue}, {yValue}, {zValue}] is outside the fixed grid")
            grid[zIndex, yIndex, xIndex] = 1
        return grid
    raise ValueError(f"unsupported 3D initializer {initialType!r}")


# :: grid3D, ((INT, INT, INT)), (INT, INT, INT), STRING, INT? -> NONE
# Places centered geometric voxels with deterministic clipping or wrapping
def _placeVoxels(
    grid: Grid3D,
    coordinates: tuple[tuple[int, int, int], ...],
    offsetCells: tuple[int, int, int],
    boundary: str,
    centerIndex: int | None = None,
) -> None:
    gridSize = grid.shape[0]
    center = centerIndex if centerIndex is not None else gridSize // 2
    offsetX, offsetY, offsetZ = offsetCells
    for xValue, yValue, zValue in coordinates:
        xIndex = center + offsetX + xValue
        yIndex = center + offsetY + yValue
        zIndex = center + offsetZ + zValue
        if boundary == "wrap":
            xIndex %= gridSize
            yIndex %= gridSize
            zIndex %= gridSize
        elif not all(0 <= value < gridSize for value in (xIndex, yIndex, zIndex)):
            continue
        grid[zIndex, yIndex, xIndex] = 1
