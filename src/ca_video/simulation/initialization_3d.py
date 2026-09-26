from __future__ import annotations  # Enable forward references in type annotations

import numpy as np  # Construct deterministic voxel grids
from numpy.typing import NDArray  # Describe NumPy voxel grids

Grid3D = NDArray[np.uint8]


# :: INT, STRING, FLOAT, INT, INT, ((INT, INT, INT)), STRING, STRING -> grid3D
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
) -> Grid3D:
    if initialType == "random":
        randomGenerator = np.random.default_rng(seed)
        return (randomGenerator.random((gridSize, gridSize, gridSize)) < density).astype(np.uint8)
    if initialType == "single":
        grid = np.zeros((gridSize, gridSize, gridSize), dtype=np.uint8)
        center = gridSize // 2
        grid[center, center, center] = 1
        return grid
    if initialType == "cross":
        grid = np.zeros((gridSize, gridSize, gridSize), dtype=np.uint8)
        center = gridSize // 2
        grid[center, center, center] = 1
        for deltaZ, deltaY, deltaX in (
            (-1, 0, 0),
            (1, 0, 0),
            (0, -1, 0),
            (0, 1, 0),
            (0, 0, -1),
            (0, 0, 1),
        ):
            grid[center + deltaZ, center + deltaY, center + deltaX] = 1
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
        start = (gridSize - len(axis)) // 2
        grid[start : start + len(axis), start : start + len(axis), start : start + len(axis)] = filled
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
