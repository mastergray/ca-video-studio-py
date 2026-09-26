from __future__ import annotations  # Enable forward references in type annotations

import numpy as np  # Store and evolve cellular-automata grids
from numpy.typing import NDArray  # Describe NumPy array types

Grid = NDArray[np.uint8]


# Evolves deterministic Conway's Life grids with wrapped or fixed boundaries
class LifeEngine:

    # CONSTRUCTOR :: grid, STRING -> lifeEngine
    # Creates an engine from an existing two-dimensional grid
    def __init__(self, grid: Grid, boundary: str = "wrap") -> None:
        if grid.ndim != 2:
            raise ValueError("Life grid must be two-dimensional")
        if boundary not in {"wrap", "fixed"}:
            raise ValueError("boundary must be wrap or fixed")
        self._grid = (grid != 0).astype(np.uint8, copy=True)
        self._boundary = boundary
        self._generation = 0

    #
    # Properties
    #

    # PROPERTY :: VOID -> grid
    # Returns the current cell grid
    @property
    def grid(self) -> Grid:
        return self._grid

    # PROPERTY :: VOID -> STRING
    # Returns the configured boundary mode
    @property
    def boundary(self) -> str:
        return self._boundary

    # PROPERTY :: VOID -> INT
    # Returns the current generation number
    @property
    def generation(self) -> int:
        return self._generation

    # PROPERTY :: VOID -> INT
    # Returns the number of live cells
    @property
    def liveCount(self) -> int:
        return int(self._grid.sum())

    #
    # Instance Methods
    #

    # :: VOID -> grid
    # Advances the automaton by one generation
    def step(self) -> Grid:
        neighbors = self._neighborCount()
        alive = self._grid == 1
        self._grid = ((neighbors == 3) | (alive & (neighbors == 2))).astype(np.uint8)
        self._generation += 1
        return self._grid

    #
    # Protected Methods
    #

    # :: VOID -> grid
    # Counts live neighbors for every cell
    def _neighborCount(self) -> NDArray[np.uint8]:
        grid = self._grid
        if self._boundary == "wrap":
            neighbors = np.zeros_like(grid, dtype=np.uint8)
            for deltaY in (-1, 0, 1):
                for deltaX in (-1, 0, 1):
                    if deltaX or deltaY:
                        neighbors += np.roll(grid, (deltaY, deltaX), axis=(0, 1))
            return neighbors

        padded = np.pad(grid, 1, mode="constant")
        height, width = grid.shape
        neighbors = np.zeros_like(grid, dtype=np.uint8)
        for deltaY in range(3):
            for deltaX in range(3):
                if deltaX != 1 or deltaY != 1:
                    neighbors += padded[deltaY : deltaY + height, deltaX : deltaX + width]
        return neighbors

    #
    # Class Methods
    #

    # Class Factory Method :: INT, INT, FLOAT, INT, STRING -> lifeEngine
    # Creates a deterministically seeded random Life grid
    @classmethod
    def init(
        cls,
        width: int,
        height: int,
        density: float,
        seed: int,
        boundary: str = "wrap",
    ) -> LifeEngine:
        randomGenerator = np.random.default_rng(seed)
        grid = (randomGenerator.random((height, width)) < density).astype(np.uint8)
        return cls(grid, boundary)
