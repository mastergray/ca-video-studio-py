from __future__ import annotations  # Enable forward references in type annotations

import numpy as np  # Store and evolve cellular-automata grids
from numpy.typing import NDArray  # Describe NumPy array types

from ca_video.simulation.rules import OuterTotalisticRule, parseRule  # Apply general B/S/C rules

Grid = NDArray[np.uint8]


# Evolves deterministic outer-totalistic grids with decay states
class OuterTotalisticEngine:

    # CONSTRUCTOR :: grid, outerTotalisticRule, STRING -> outerTotalisticEngine
    # Creates an engine from an existing two-dimensional grid
    def __init__(
        self,
        grid: Grid,
        rule: OuterTotalisticRule,
        boundary: str = "wrap",
    ) -> None:
        if grid.ndim != 2:
            raise ValueError("Life grid must be two-dimensional")
        if boundary not in {"wrap", "fixed"}:
            raise ValueError("boundary must be wrap or fixed")
        if grid.size and int(grid.max()) >= rule.states:
            raise ValueError("grid contains a state outside the rule's state range")
        self._grid = grid.astype(np.uint8, copy=True)
        self._rule = rule
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

    # PROPERTY :: VOID -> outerTotalisticRule
    # Returns the active rule
    @property
    def rule(self) -> OuterTotalisticRule:
        return self._rule

    # PROPERTY :: VOID -> INT
    # Returns the current generation number
    @property
    def generation(self) -> int:
        return self._generation

    # PROPERTY :: VOID -> INT
    # Returns the number of live cells
    @property
    def liveCount(self) -> int:
        return int(np.count_nonzero(self._grid == 1))

    #
    # Instance Methods
    #

    # :: VOID -> grid
    # Advances the automaton by one generation
    def step(self) -> Grid:
        neighbors = self._neighborCount()
        alive = self._grid == 1
        dead = self._grid == 0
        born = dead & np.isin(neighbors, self._rule.birth)
        survives = alive & np.isin(neighbors, self._rule.survival)
        nextGrid = np.zeros_like(self._grid)
        nextGrid[born | survives] = 1
        if self._rule.states > 2:
            nextGrid[alive & ~survives] = 2
            decaying = self._grid >= 2
            nextGrid[decaying & (self._grid < self._rule.states - 1)] = self._grid[
                decaying & (self._grid < self._rule.states - 1)
            ] + 1
        self._grid = nextGrid
        self._generation += 1
        return self._grid

    #
    # Protected Methods
    #

    # :: VOID -> grid
    # Counts live neighbors for every cell
    def _neighborCount(self) -> NDArray[np.uint8]:
        grid = self._grid
        offsets = (
            ((-1, 0), (1, 0), (0, -1), (0, 1))
            if self._rule.neighborhood == "von_neumann"
            else tuple(
                (deltaY, deltaX)
                for deltaY in (-1, 0, 1)
                for deltaX in (-1, 0, 1)
                if deltaX or deltaY
            )
        )
        live = (grid == 1).astype(np.uint8)
        if self._boundary == "wrap":
            neighbors = np.zeros_like(grid, dtype=np.uint8)
            for deltaY, deltaX in offsets:
                neighbors += np.roll(live, (deltaY, deltaX), axis=(0, 1))
            return neighbors

        padded = np.pad(live, 1, mode="constant")
        height, width = grid.shape
        neighbors = np.zeros_like(grid, dtype=np.uint8)
        for deltaY, deltaX in offsets:
            startY, startX = deltaY + 1, deltaX + 1
            neighbors += padded[startY : startY + height, startX : startX + width]
        return neighbors

    #
    # Class Methods
    #

    # Class Factory Method :: INT, INT, FLOAT, INT, STRING, outerTotalisticRule? -> outerTotalisticEngine
    # Creates a deterministically seeded random grid
    @classmethod
    def init(
        cls,
        width: int,
        height: int,
        density: float,
        seed: int,
        boundary: str = "wrap",
        rule: OuterTotalisticRule | None = None,
    ) -> OuterTotalisticEngine:
        randomGenerator = np.random.default_rng(seed)
        grid = (randomGenerator.random((height, width)) < density).astype(np.uint8)
        return cls(grid, rule or parseRule("B3/S23"), boundary)


# Preserves the original vertical-slice API for callers that need Conway Life
class LifeEngine(OuterTotalisticEngine):

    # CONSTRUCTOR :: grid, STRING -> lifeEngine
    # Creates a Conway Life engine from an existing grid
    def __init__(self, grid: Grid, boundary: str = "wrap") -> None:
        super().__init__(grid, parseRule("B3/S23"), boundary)

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
