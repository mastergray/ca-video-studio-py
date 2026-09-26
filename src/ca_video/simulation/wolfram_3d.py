from __future__ import annotations  # Enable forward references in type annotations

import numpy as np  # Store and evolve extruded elementary histories
from numpy.typing import NDArray  # Describe Wolfram rows and voxel grids

Grid3D = NDArray[np.uint8]
Row = NDArray[np.uint8]


# Evolves an elementary automaton as a positionable extruded 3D history
class WolframEngine3D:

    # CONSTRUCTOR :: INT, INT, STRING, FLOAT, INT, (INT), INT, INT -> wolframEngine3D
    # Creates a deterministic, prefilled extruded Wolfram volume
    def __init__(
        self,
        gridSize: int,
        ruleNumber: int,
        initialType: str = "single_center",
        density: float = 0.5,
        seed: int = 0,
        bits: tuple[int, ...] = (),
        extrusionDepth: int | None = None,
        extrusionOffset: int = 0,
    ) -> None:
        if gridSize < 1:
            raise ValueError("Wolfram 3D grid size must be positive")
        if not 0 <= ruleNumber <= 255:
            raise ValueError("Wolfram rule number must be between 0 and 255")
        if initialType not in {"single_center", "random", "bits"}:
            raise ValueError("unsupported Wolfram initial row type")
        if not 0 <= density <= 1:
            raise ValueError("Wolfram random density must be between 0 and 1")
        if initialType == "bits" and not bits:
            raise ValueError("explicit Wolfram bits must not be empty")
        if len(bits) > gridSize:
            raise ValueError("explicit Wolfram bits are wider than the grid")
        if any(bit not in {0, 1} for bit in bits):
            raise ValueError("explicit Wolfram bits must contain only zero and one")
        resolvedDepth = extrusionDepth if extrusionDepth is not None else max(1, gridSize // 4)
        if not 1 <= resolvedDepth <= gridSize:
            raise ValueError("Wolfram extrusion depth must fit within the grid")
        if not -gridSize <= extrusionOffset <= gridSize:
            raise ValueError("Wolfram extrusion offset must not exceed the grid size")

        self._ruleNumber = ruleNumber
        self._extrusionDepth = resolvedDepth
        self._extrusionOffset = extrusionOffset
        self._generation = 0
        self._row = self._initialRow(gridSize, initialType, density, seed, bits)
        self._grid = np.zeros((gridSize, gridSize, gridSize), dtype=np.uint8)
        for zIndex in range(gridSize):
            self._writeSlice(zIndex, self._row)
            self._row = self._nextRow(self._row)

    # PROPERTY :: VOID -> grid3D
    # Returns the current extruded scrolling history in z, y, x order
    @property
    def grid(self) -> Grid3D:
        return self._grid

    # PROPERTY :: VOID -> row
    # Returns the next source row beyond the visible history
    @property
    def row(self) -> Row:
        return self._row

    # PROPERTY :: VOID -> INT
    # Returns the configured elementary rule number
    @property
    def ruleNumber(self) -> int:
        return self._ruleNumber

    # PROPERTY :: VOID -> INT
    # Returns the centered extrusion band thickness
    @property
    def extrusionDepth(self) -> int:
        return self._extrusionDepth

    # PROPERTY :: VOID -> INT
    # Returns the extrusion band's displacement along the Y axis
    @property
    def extrusionOffset(self) -> int:
        return self._extrusionOffset

    # PROPERTY :: VOID -> INT
    # Returns the number of scrolling steps since initialization
    @property
    def generation(self) -> int:
        return self._generation

    # PROPERTY :: VOID -> INT
    # Returns the number of occupied voxels in the visible history
    @property
    def liveCount(self) -> int:
        return int(np.count_nonzero(self._grid))

    # :: VOID -> grid3D
    # Shifts the volume and appends one newly evolved extruded row
    def step(self) -> Grid3D:
        nextRow = self._nextRow(self._row)
        self._grid[:-1] = self._grid[1:]
        self._grid[-1] = 0
        self._writeSlice(self._grid.shape[0] - 1, nextRow)
        self._row = nextRow
        self._generation += 1
        return self._grid

    # :: INT, STRING, FLOAT, INT, (INT) -> row
    # Builds the configured deterministic starting row
    def _initialRow(
        self,
        width: int,
        initialType: str,
        density: float,
        seed: int,
        bits: tuple[int, ...],
    ) -> Row:
        if initialType == "random":
            randomGenerator = np.random.default_rng(seed)
            return (randomGenerator.random(width) < density).astype(np.uint8)
        row = np.zeros(width, dtype=np.uint8)
        if initialType == "single_center":
            row[width // 2] = 1
            return row
        offset = (width - len(bits)) // 2
        row[offset : offset + len(bits)] = bits
        return row

    # :: row -> row
    # Applies the elementary truth table with wrapped horizontal neighbors
    def _nextRow(self, row: Row) -> Row:
        left = np.roll(row, 1)
        right = np.roll(row, -1)
        patterns = (left << 2) | (row << 1) | right
        return ((self._ruleNumber >> patterns) & 1).astype(np.uint8)

    # :: INT, row -> NONE
    # Writes one row through the offset Y-axis extrusion band with fixed clipping
    def _writeSlice(self, zIndex: int, row: Row) -> None:
        startY = (self._grid.shape[1] - self._extrusionDepth) // 2 + self._extrusionOffset
        endY = startY + self._extrusionDepth
        clippedStart = max(0, startY)
        clippedEnd = min(self._grid.shape[1], endY)
        if clippedStart < clippedEnd:
            self._grid[zIndex, clippedStart:clippedEnd, :] = row

    # Class Factory Method :: INT, INT, INT, INT -> wolframEngine3D
    # Creates an inert zero volume for a disabled layer
    @classmethod
    def blank(
        cls,
        gridSize: int,
        ruleNumber: int,
        extrusionDepth: int,
        extrusionOffset: int = 0,
    ) -> WolframEngine3D:
        instance = cls.__new__(cls)
        instance._ruleNumber = ruleNumber
        instance._extrusionDepth = extrusionDepth
        instance._extrusionOffset = extrusionOffset
        instance._generation = 0
        instance._row = np.zeros(gridSize, dtype=np.uint8)
        instance._grid = np.zeros((gridSize, gridSize, gridSize), dtype=np.uint8)
        return instance
