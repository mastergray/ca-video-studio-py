from __future__ import annotations  # Enable forward references in type annotations

import hashlib  # Derive stable per-layer random seeds

import numpy as np  # Create frame buffers and disabled-layer grids
from numpy.typing import NDArray  # Describe NumPy array types

from ca_video.config.models import Layer2DConfig, ProjectConfig  # Read validated project settings
from ca_video.rendering.renderer_2d import Renderer2D  # Render transparent layer frames
from ca_video.simulation.initialization import initializeGrid  # Build configured starting grids
from ca_video.simulation.life import OuterTotalisticEngine  # Evolve general B/S/C automata


# :: INT, STRING -> INT
# Derives a stable per-layer seed without Python's randomized hash function
def stableLayerSeed(masterSeed: int, layerId: str) -> int:
    payload = f"ca-video-v1:{masterSeed}:{layerId}".encode()
    return int.from_bytes(hashlib.blake2b(payload, digest_size=8).digest(), "big")


# Coordinates independent simulations and ordered alpha composition
class ProjectRuntime:

    # CONSTRUCTOR :: projectConfig -> projectRuntime
    # Creates a deterministic runtime for every configured layer
    def __init__(self, project: ProjectConfig) -> None:
        self._project = project
        self._currentFrameIndex = 0
        self._engines: dict[str, OuterTotalisticEngine] = {}
        self._renderers: dict[str, Renderer2D] = {}
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
    # Returns the first layer engine for single-layer compatibility
    @property
    def engine(self) -> OuterTotalisticEngine:
        return self._engines[self._project.layer.id]

    # PROPERTY :: VOID -> INT
    # Returns the most recently rendered frame index
    @property
    def currentFrameIndex(self) -> int:
        return self._currentFrameIndex

    #
    # Instance Methods
    #

    # :: INT -> outerTotalisticEngine
    # Returns the engine for a layer in editor order
    def engineForLayer(self, layerIndex: int) -> OuterTotalisticEngine:
        layer = self._project.layers[layerIndex]
        return self._engines[layer.id]

    # :: VOID -> NONE
    # Restores every deterministic initial simulation state
    def reset(self) -> None:
        self._engines = {
            layer.id: self._createEngine(layer)
            for layer in self._project.layers
        }
        self._buildRenderers()
        self._currentFrameIndex = 0

    # :: projectConfig, BOOL -> rgbFrame
    # Reconfigures appearance while optionally rebuilding simulations
    def updateProject(self, project: ProjectConfig, resetSimulation: bool) -> NDArray[np.uint8]:
        previousIds = tuple(layer.id for layer in self._project.layers)
        nextIds = tuple(layer.id for layer in project.layers)
        self._project = project
        if resetSimulation or previousIds != nextIds:
            self.reset()
        else:
            self._buildRenderers()
        return self._composite()

    # :: INT -> rgbFrame
    # Advances deterministically to and renders a requested output frame
    def renderFrame(self, frameIndex: int) -> NDArray[np.uint8]:
        if frameIndex < self._currentFrameIndex:
            self.reset()
        for layer in self._project.layers:
            if not layer.enabled:
                continue
            engine = self._engines[layer.id]
            targetGeneration = self._generationDue(layer, frameIndex)
            while engine.generation < targetGeneration:
                engine.step()
        self._currentFrameIndex = frameIndex
        return self._composite()

    # :: VOID -> rgbFrame
    # Advances every enabled layer by exactly one generation
    def stepOnce(self) -> NDArray[np.uint8]:
        frameCandidates = [self._currentFrameIndex]
        for layer in self._project.layers:
            if not layer.enabled:
                continue
            engine = self._engines[layer.id]
            engine.step()
            numerator = engine.generation * layer.stepIntervalMs * self._project.output.fps
            frameCandidates.append((numerator + 999) // 1000)
        self._currentFrameIndex = max(frameCandidates)
        return self._composite()

    #
    # Protected Methods
    #

    # :: layer2DConfig -> outerTotalisticEngine
    # Creates one deterministically initialized layer engine
    def _createEngine(self, layer: Layer2DConfig) -> OuterTotalisticEngine:
        if not layer.enabled:
            grid = np.zeros((layer.gridHeight, layer.gridWidth), dtype=np.uint8)
            return OuterTotalisticEngine(grid, layer.rule, layer.boundary)
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
        return OuterTotalisticEngine(grid, layer.rule, layer.boundary)

    # :: VOID -> NONE
    # Rebuilds renderers for the current output and layer appearances
    def _buildRenderers(self) -> None:
        output = self._project.output
        self._renderers = {
            layer.id: Renderer2D(
                output.width,
                output.height,
                self._project.canvasBackground,
                layer.liveColor,
                layer.opacity,
                layer.layout,
                layer.rule.states,
            )
            for layer in self._project.layers
        }

    # :: VOID -> rgbFrame
    # Composites enabled layers by z-index and stable editor order
    def _composite(self) -> NDArray[np.uint8]:
        output = self._project.output
        frame = np.empty((output.height, output.width, 3), dtype=np.float32)
        frame[:] = self._project.canvasBackground
        indexedLayers = enumerate(self._project.layers)
        for _, layer in sorted(indexedLayers, key=lambda item: (item[1].zIndex, item[0])):
            if not layer.enabled:
                continue
            rendered = self._renderers[layer.id].renderLayer(self._engines[layer.id].grid)
            alpha = rendered[..., 3:4]
            frame = frame * (1.0 - alpha) + rendered[..., :3] * alpha
        return frame.clip(0, 255).astype(np.uint8)

    # :: layer2DConfig, INT -> INT
    # Calculates the generation due at an output frame using integer time
    def _generationDue(self, layer: Layer2DConfig, frameIndex: int) -> int:
        return (frameIndex * 1000) // (layer.stepIntervalMs * self._project.output.fps)
