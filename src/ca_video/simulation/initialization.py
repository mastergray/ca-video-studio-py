from __future__ import annotations  # Enable forward references in type annotations

import re  # Parse run-length encoded Life patterns
from pathlib import Path  # Resolve RLE source files

import numpy as np  # Construct deterministic cell grids
from numpy.typing import NDArray  # Describe NumPy grids

Grid = NDArray[np.uint8]
RLE_HEADER = re.compile(r"x\s*=\s*(\d+)\s*,\s*y\s*=\s*(\d+)(?:\s*,.*)?$", re.IGNORECASE)
RLE_TOKEN = re.compile(r"(\d*)([bo$!])", re.IGNORECASE)


# :: INT, INT, STRING, FLOAT, INT, INT, (INT, INT)?, ((INT, INT))?, STRING, STRING?, path? -> grid
# Creates a grid from a validated initialization description
def initializeGrid(
    width: int,
    height: int,
    initialType: str,
    density: float,
    radius: int,
    seed: int,
    size: tuple[int, int] | None = None,
    cells: tuple[tuple[int, int], ...] = (),
    origin: str = "center",
    rleData: str | None = None,
    rlePath: Path | None = None,
    boundary: str = "wrap",
) -> Grid:
    if initialType == "random":
        randomGenerator = np.random.default_rng(seed)
        return (randomGenerator.random((height, width)) < density).astype(np.uint8)
    if initialType == "center_block":
        blockWidth, blockHeight = size or (radius * 2 + 1, radius * 2 + 1)
        mask = np.ones((blockHeight, blockWidth), dtype=bool)
        return _placeMask(width, height, mask, density, seed)
    if initialType == "disc":
        axis = np.arange(-radius, radius + 1)
        mask = axis[:, None] ** 2 + axis[None, :] ** 2 <= radius**2
        return _placeMask(width, height, mask, density, seed)
    if initialType == "cells":
        grid = np.zeros((height, width), dtype=np.uint8)
        offsetX = width // 2 if origin == "center" else 0
        offsetY = height // 2 if origin == "center" else 0
        for xValue, yValue in cells:
            xIndex, yIndex = xValue + offsetX, yValue + offsetY
            if boundary == "wrap":
                xIndex %= width
                yIndex %= height
            elif not (0 <= xIndex < width and 0 <= yIndex < height):
                raise ValueError(f"cell [{xValue}, {yValue}] is outside the fixed grid")
            grid[yIndex, xIndex] = 1
        return grid
    if initialType == "rle":
        if rlePath is not None:
            try:
                rleData = rlePath.read_text(encoding="utf-8")
            except OSError as error:
                raise ValueError(f"could not read RLE file {rlePath}: {error}") from error
        if rleData is None:
            raise ValueError("RLE initialization requires inline data or a file")
        pattern = parseRle(rleData)
        return _placePattern(width, height, pattern, boundary)
    raise ValueError(f"unsupported initializer {initialType!r}")


# :: STRING -> grid
# Parses standard two-state Life RLE into a tightly bounded grid
def parseRle(value: str) -> Grid:
    lines = [line.strip() for line in value.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    if not lines:
        raise ValueError("RLE data is empty")
    header = RLE_HEADER.fullmatch(lines[0])
    if not header:
        raise ValueError("RLE header must declare x and y")
    width, height = int(header.group(1)), int(header.group(2))
    if width < 1 or height < 1:
        raise ValueError("RLE dimensions must be positive")
    body = "".join(lines[1:]).replace(" ", "")
    tokens = list(RLE_TOKEN.finditer(body))
    if not tokens or "".join(token.group(0) for token in tokens) != body:
        raise ValueError("RLE body contains unsupported symbols")
    grid = np.zeros((height, width), dtype=np.uint8)
    xIndex = yIndex = 0
    ended = False
    for token in tokens:
        count = int(token.group(1) or 1)
        symbol = token.group(2).lower()
        if symbol == "!":
            if count != 1 or token is not tokens[-1]:
                raise ValueError("RLE terminator must appear once at the end")
            ended = True
            continue
        if symbol == "$":
            yIndex += count
            xIndex = 0
            if yIndex > height:
                raise ValueError("RLE pattern exceeds its declared height")
            continue
        if yIndex >= height or xIndex + count > width:
            raise ValueError("RLE pattern exceeds its declared dimensions")
        if symbol == "o":
            grid[yIndex, xIndex : xIndex + count] = 1
        xIndex += count
    if not ended:
        raise ValueError("RLE body is missing the ! terminator")
    return grid


# :: INT, INT, grid, FLOAT, INT -> grid
# Centers a geometric mask and fills it with deterministic density
def _placeMask(width: int, height: int, mask: NDArray[np.bool_], density: float, seed: int) -> Grid:
    maskHeight, maskWidth = mask.shape
    if maskWidth > width or maskHeight > height:
        raise ValueError("initial shape is larger than the grid")
    randomGenerator = np.random.default_rng(seed)
    filled = mask & (randomGenerator.random(mask.shape) < density)
    grid = np.zeros((height, width), dtype=np.uint8)
    startX = (width - maskWidth) // 2
    startY = (height - maskHeight) // 2
    grid[startY : startY + maskHeight, startX : startX + maskWidth] = filled
    return grid


# :: INT, INT, grid, STRING -> grid
# Centers an RLE pattern with fixed-boundary checks or deterministic wrapping
def _placePattern(width: int, height: int, pattern: Grid, boundary: str) -> Grid:
    patternHeight, patternWidth = pattern.shape
    if boundary == "fixed" and (patternWidth > width or patternHeight > height):
        raise ValueError("RLE pattern is larger than the fixed grid")
    grid = np.zeros((height, width), dtype=np.uint8)
    offsetX = (width - patternWidth) // 2
    offsetY = (height - patternHeight) // 2
    for yValue, xValue in np.argwhere(pattern == 1):
        xIndex, yIndex = xValue + offsetX, yValue + offsetY
        if boundary == "wrap":
            xIndex %= width
            yIndex %= height
        elif not (0 <= xIndex < width and 0 <= yIndex < height):
            raise ValueError("RLE pattern is outside the fixed grid")
        grid[yIndex, xIndex] = 1
    return grid
