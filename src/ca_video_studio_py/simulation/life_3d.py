from __future__ import annotations  # Enable forward references in type annotations

import numpy as np  # Store and evolve three-dimensional cellular grids
from numpy.typing import NDArray  # Describe NumPy voxel grids

from ca_video_studio_py.simulation.rules import OuterTotalisticRule  # Apply general B/S/C rules

Grid3D = NDArray[np.uint8]


# Evolves deterministic outer-totalistic voxel grids
class OuterTotalisticEngine3D:

    # CONSTRUCTOR :: grid3D, outerTotalisticRule, STRING -> outerTotalisticEngine3D
    # Creates an engine from an existing cubic voxel grid
    def __init__(self, grid: Grid3D, rule: OuterTotalisticRule, boundary: str = "fixed") -> None:
        if grid.ndim != 3 or len(set(grid.shape)) != 1:
            raise ValueError("3D grid must be cubic")
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

    # PROPERTY :: VOID -> grid3D
    # Returns the current voxel grid in z, y, x order
    @property
    def grid(self) -> Grid3D:
        return self._grid

    # PROPERTY :: VOID -> outerTotalisticRule
    # Returns the active rule
    @property
    def rule(self) -> OuterTotalisticRule:
        return self._rule

    # PROPERTY :: VOID -> STRING
    # Returns the configured boundary behavior
    @property
    def boundary(self) -> str:
        return self._boundary

    # PROPERTY :: VOID -> INT
    # Returns the current generation number
    @property
    def generation(self) -> int:
        return self._generation

    # PROPERTY :: VOID -> INT
    # Returns the number of live voxels
    @property
    def liveCount(self) -> int:
        return int(np.count_nonzero(self._grid == 1))

    #
    # Instance Methods
    #

    # :: VOID -> grid3D
    # Advances the automaton by one generation
    def step(self) -> Grid3D:
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
            advances = decaying & (self._grid < self._rule.states - 1)
            nextGrid[advances] = self._grid[advances] + 1
        self._grid = nextGrid
        self._generation += 1
        return self._grid

    #
    # Protected Methods
    #

    # :: VOID -> grid3D
    # Counts live neighbors for every voxel
    def _neighborCount(self) -> Grid3D:
        offsets = (
            ((-1, 0, 0), (1, 0, 0), (0, -1, 0), (0, 1, 0), (0, 0, -1), (0, 0, 1))
            if self._rule.neighborhood == "von_neumann"
            else tuple(
                (deltaZ, deltaY, deltaX)
                for deltaZ in (-1, 0, 1)
                for deltaY in (-1, 0, 1)
                for deltaX in (-1, 0, 1)
                if deltaX or deltaY or deltaZ
            )
        )
        live = (self._grid == 1).astype(np.uint8)
        if self._boundary == "wrap":
            neighbors = np.zeros_like(live)
            for offset in offsets:
                neighbors += np.roll(live, offset, axis=(0, 1, 2))
            return neighbors

        padded = np.pad(live, 1, mode="constant")
        size = self._grid.shape[0]
        neighbors = np.zeros_like(live)
        for deltaZ, deltaY, deltaX in offsets:
            startZ, startY, startX = deltaZ + 1, deltaY + 1, deltaX + 1
            neighbors += padded[
                startZ : startZ + size,
                startY : startY + size,
                startX : startX + size,
            ]
        return neighbors
