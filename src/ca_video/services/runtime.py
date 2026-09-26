from __future__ import annotations  # Enable forward references in type annotations

import hashlib  # Derive stable per-layer random seeds

import numpy as np  # Create disabled-layer grids and type frame arrays
from numpy.typing import NDArray  # Describe NumPy array types

from ca_video.config.models import ProjectConfig  # Read validated project settings
from ca_video.rendering.renderer_2d import Renderer2D  # Render simulation grids
from ca_video.simulation.initialization import initializeGrid  # Build configured starting grids
from ca_video.simulation.life import OuterTotalisticEngine  # Evolve general B/S/C automata


# :: INT, STRING -> INT
# Derives a stable per-layer seed without Python's randomized hash function
def stableLayerSeed(masterSeed: int, layerId: str) -> int:
    payload = f"ca-video-v1:{masterSeed}:{layerId}".encode()
    return int.from_bytes(hashlib.blake2b(payload, digest_size=8).digest(), "big")


# Coordinates deterministic simulation and rendering for preview and export
class ProjectRuntime:

    # CONSTRUCTOR :: projectConfig -> projectRuntime
    # Creates a runtime for a validated project
    def __init__(self, project: ProjectConfig) -> None:
        self._project = project
        self._renderer = Renderer2D(
            project.output.width,
            project.output.height,
            project.canvasBackground,
            project.layer.liveColor,
            project.layer.opacity,
            project.layer.layout,
            project.layer.rule.states,
        )
        self._currentFrameIndex = 0
        self.reset()

    #
    # Properties
    #

    # PROPERTY :: VOID -> projectConfig
    # Returns the active project settings
    @property
    def project(self) -> ProjectConfig:
        return self._project

    # PROPERTY :: VOID -> outerTotalisticEngine
    # Returns the current automaton engine
    @property
    def engine(self) -> OuterTotalisticEngine:
        return self._engine

    # PROPERTY :: VOID -> INT
    # Returns the most recently rendered frame index
    @property
    def currentFrameIndex(self) -> int:
        return self._currentFrameIndex

    #
    # Instance Methods
    #

    # :: VOID -> NONE
    # Restores the deterministic initial simulation state
    def reset(self) -> None:
        layer = self._project.layer
        if layer.enabled:
            initial = layer.initial
            rlePath = initial.rlePath
            if rlePath is not None and not rlePath.is_absolute():
                rlePath = self._project.baseDir / rlePath
            grid = initializeGrid(
                layer.gridWidth,
                layer.gridHeight,
                initial.type,
                initial.density,
                initial.radius,
                stableLayerSeed(self._project.seed, layer.id),
                initial.size,
                initial.cells,
                initial.origin,
                initial.rleData,
                rlePath,
                layer.boundary,
            )
            self._engine = OuterTotalisticEngine(grid, layer.rule, layer.boundary)
        else:
            emptyGrid = np.zeros((layer.gridHeight, layer.gridWidth), dtype=np.uint8)
            self._engine = OuterTotalisticEngine(emptyGrid, layer.rule, layer.boundary)
        self._currentFrameIndex = 0

    # :: projectConfig, BOOL -> rgbFrame
    # Reconfigures rendering while optionally preserving simulation state
    def updateProject(self, project: ProjectConfig, resetSimulation: bool) -> NDArray[np.uint8]:
        self._project = project
        self._renderer = Renderer2D(
            project.output.width,
            project.output.height,
            project.canvasBackground,
            project.layer.liveColor,
            project.layer.opacity,
            project.layer.layout,
            project.layer.rule.states,
        )
        if resetSimulation:
            self.reset()
        return self._renderer.render(self._engine.grid)

    # :: INT -> rgbFrame
    # Advances deterministically to and renders a requested output frame
    def renderFrame(self, frameIndex: int) -> NDArray[np.uint8]:
        if frameIndex < self._currentFrameIndex:
            self.reset()
        if self._project.layer.enabled:
            targetGeneration = self._generationDue(frameIndex)
            while self._engine.generation < targetGeneration:
                self._engine.step()
        self._currentFrameIndex = frameIndex
        return self._renderer.render(self._engine.grid)

    # :: VOID -> rgbFrame
    # Advances exactly one generation and renders it
    def stepOnce(self) -> NDArray[np.uint8]:
        if self._project.layer.enabled:
            self._engine.step()
        numerator = (
            self._engine.generation
            * self._project.layer.stepIntervalMs
            * self._project.output.fps
        )
        self._currentFrameIndex = max(self._currentFrameIndex, (numerator + 999) // 1000)
        return self._renderer.render(self._engine.grid)

    #
    # Protected Methods
    #

    # :: INT -> INT
    # Calculates the generation due at an output frame using integer time
    def _generationDue(self, frameIndex: int) -> int:
        layer = self._project.layer
        return (frameIndex * 1000) // (layer.stepIntervalMs * self._project.output.fps)
