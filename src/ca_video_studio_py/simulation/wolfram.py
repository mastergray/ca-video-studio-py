from __future__ import annotations  # Enable forward references in type annotations

import numpy as np  # Store and evolve elementary cellular-automata histories
from numpy.typing import NDArray  # Describe row and grid arrays

Grid = NDArray[np.uint8]
Row = NDArray[np.uint8]


# Evolves an elementary one-dimensional automaton as a scrolling 2D history
class WolframEngine:

    # CONSTRUCTOR :: INT, INT, INT, STRING, FLOAT, INT, (INT) -> wolframEngine
    # Creates a deterministic, prefilled Wolfram history
    def __init__(
        self,
        width: int,
        height: int,
        ruleNumber: int,
        initialType: str = "single_center",
        density: float = 0.5,
        seed: int = 0,
        bits: tuple[int, ...] = (),
    ) -> None:
        if width < 1 or height < 1:
            raise ValueError("Wolfram grid dimensions must be positive")
        if not 0 <= ruleNumber <= 255:
            raise ValueError("Wolfram rule number must be between 0 and 255")
        if initialType not in {"single_center", "random", "bits"}:
            raise ValueError("unsupported Wolfram initial row type")
        if not 0 <= density <= 1:
            raise ValueError("Wolfram random density must be between 0 and 1")
        if initialType == "bits" and not bits:
            raise ValueError("explicit Wolfram bits must not be empty")
        if len(bits) > width:
            raise ValueError("explicit Wolfram bits are wider than the grid")
        if any(bit not in {0, 1} for bit in bits):
            raise ValueError("explicit Wolfram bits must contain only zero and one")

        self._ruleNumber = ruleNumber
        self._generation = 0
        self._row = self._initialRow(width, initialType, density, seed, bits)
        self._grid = np.zeros((height, width), dtype=np.uint8)
        for rowIndex in range(height):
            self._grid[rowIndex] = self._row
            if rowIndex < height - 1:
                self._row = self._nextRow(self._row)

    #
    # Properties
    #

    # PROPERTY :: VOID -> grid
    # Returns the current scrolling history
    @property
    def grid(self) -> Grid:
        return self._grid

    # PROPERTY :: VOID -> row
    # Returns the newest row in the visible history
    @property
    def row(self) -> Row:
        return self._row

    # PROPERTY :: VOID -> INT
    # Returns the configured elementary rule number
    @property
    def ruleNumber(self) -> int:
        return self._ruleNumber

    # PROPERTY :: VOID -> INT
    # Returns the number of scrolling steps since initialization
    @property
    def generation(self) -> int:
        return self._generation

    # PROPERTY :: VOID -> INT
    # Returns the number of live cells in the visible history
    @property
    def liveCount(self) -> int:
        return int(np.count_nonzero(self._grid))

    #
    # Instance Methods
    #

    # :: VOID -> grid
    # Scrolls the history and appends one newly evolved row
    def step(self) -> Grid:
        nextRow = self._nextRow(self._row)
        self._grid[:-1] = self._grid[1:]
        self._grid[-1] = nextRow
        self._row = nextRow
        self._generation += 1
        return self._grid

    #
    # Protected Methods
    #

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

    #
    # Class Methods
    #

    # Class Factory Method :: INT, INT, INT -> wolframEngine
    # Creates an inert zero history for a disabled layer
    @classmethod
    def blank(cls, width: int, height: int, ruleNumber: int) -> WolframEngine:
        instance = cls.__new__(cls)
        instance._ruleNumber = ruleNumber
        instance._generation = 0
        instance._row = np.zeros(width, dtype=np.uint8)
        instance._grid = np.zeros((height, width), dtype=np.uint8)
        return instance
