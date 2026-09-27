from __future__ import annotations  # Enable forward references in type annotations

import numpy as np  # Maintain deterministic logical-cell trail memory
from numpy.typing import NDArray  # Describe simulation grids and trail buffers

Grid = NDArray[np.uint8]
TrailBuffer = NDArray[np.float32]
REFERENCE_TRAIL_FPS = 30


# Tracks two-dimensional live-cell history independently from simulation state
class TrailState:

    # CONSTRUCTOR :: grid -> trailState
    # Seeds trail memory from initially live state-one cells
    def __init__(self, grid: Grid) -> None:
        self._values = (grid == 1).astype(np.float32)
        self._anchorValues = self._values.copy()
        self._live = grid == 1
        self._anchorSeconds = 0.0

    # PROPERTY :: VOID -> trailBuffer
    # Returns current logical-cell trail intensity from zero through one
    @property
    def values(self) -> TrailBuffer:
        return self._values

    # :: grid, FLOAT, FLOAT -> NONE
    # Commits a simulation transition at its exact presentation time
    def transition(self, grid: Grid, amount: float, presentationSeconds: float) -> None:
        self._values = self._valueAt(amount, presentationSeconds)
        self._anchorValues = self._values.copy()
        self._anchorSeconds = presentationSeconds
        self._live = grid == 1
        self._anchorValues[self._live] = 1
        self._values[self._live] = 1
        if amount <= 0:
            self._anchorValues[~self._live] = 0
            self._values[~self._live] = 0

    # :: FLOAT, FLOAT -> NONE
    # Samples trail decay without changing its transition-time anchor
    def sample(self, amount: float, presentationSeconds: float) -> None:
        if presentationSeconds < self._anchorSeconds:
            raise ValueError("trail presentation time must not move backward")
        self._values = self._valueAt(amount, presentationSeconds)

    # :: FLOAT, FLOAT -> NONE
    # Preserves current trail memory when its retention amount changes
    def rebase(self, amount: float, presentationSeconds: float) -> None:
        self._values = self._valueAt(amount, presentationSeconds)
        self._anchorValues = self._values.copy()
        self._anchorSeconds = presentationSeconds

    # :: FLOAT, FLOAT -> trailBuffer
    # Evaluates continuous decay using the reference 30-fps retention meaning
    def _valueAt(self, amount: float, presentationSeconds: float) -> TrailBuffer:
        values = self._anchorValues.copy()
        values[self._live] = 1
        if amount <= 0:
            values[~self._live] = 0
            return values
        elapsedFrames = max(0, presentationSeconds - self._anchorSeconds) * REFERENCE_TRAIL_FPS
        values[~self._live] *= amount**elapsedFrames
        return values
