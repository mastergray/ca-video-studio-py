from __future__ import annotations  # Enable forward references in type annotations

import numpy as np  # Maintain deterministic per-cell visual interpolation
from numpy.typing import NDArray  # Describe logical grids and fade buffers

Grid = NDArray[np.uint8]
Presence = NDArray[np.float32]


# Tracks visual presence independently from automaton state
class FadeState:

    # CONSTRUCTOR :: grid -> fadeState
    # Creates a fully visible initial state while retaining its cell values
    def __init__(self, grid: Grid) -> None:
        self._presence = (grid > 0).astype(np.float32)
        self._displayGrid = grid.copy()
        self._anchorPresence = self._presence.copy()
        self._target = self._presence.copy()
        self._anchorSeconds = 0.0

    # PROPERTY :: VOID -> presence
    # Returns per-cell visual presence from zero through one
    @property
    def presence(self) -> Presence:
        return self._presence

    # PROPERTY :: VOID -> grid
    # Returns current or last-live states for stable fade-out coloring
    @property
    def displayGrid(self) -> Grid:
        return self._displayGrid

    # :: grid, FLOAT, FLOAT -> NONE
    # Commits a simulation transition at its exact presentation time
    def transition(self, grid: Grid, fadeRate: float, presentationSeconds: float) -> None:
        self._presence = self._valueAt(fadeRate, presentationSeconds)
        self._anchorPresence = self._presence.copy()
        self._anchorSeconds = presentationSeconds
        self._target = (grid > 0).astype(np.float32)
        live = grid > 0
        self._displayGrid[live] = grid[live]
        if fadeRate <= 0:
            self._presence = self._target.copy()
            self._anchorPresence = self._presence.copy()

    # :: grid, FLOAT, FLOAT -> NONE
    # Samples visual presence without changing its transition-time anchor
    def sample(self, grid: Grid, fadeRate: float, presentationSeconds: float) -> None:
        if presentationSeconds < self._anchorSeconds:
            raise ValueError("fade presentation time must not move backward")
        live = grid > 0
        self._displayGrid[live] = grid[live]
        self._presence = self._valueAt(fadeRate, presentationSeconds)

    # :: FLOAT, FLOAT -> NONE
    # Preserves the current appearance when its interpolation rate changes
    def rebase(self, fadeRate: float, presentationSeconds: float) -> None:
        self._presence = self._valueAt(fadeRate, presentationSeconds)
        self._anchorPresence = self._presence.copy()
        self._anchorSeconds = presentationSeconds

    # :: FLOAT, FLOAT -> presence
    # Evaluates the current linear segment independently of sampling frequency
    def _valueAt(self, fadeRate: float, presentationSeconds: float) -> Presence:
        if fadeRate <= 0:
            return self._target.copy()
        change = fadeRate * max(0, presentationSeconds - self._anchorSeconds)
        difference = self._target - self._anchorPresence
        return self._anchorPresence + np.clip(difference, -change, change)
