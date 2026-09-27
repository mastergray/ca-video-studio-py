from __future__ import annotations  # Enable forward references in type annotations

import hashlib  # Derive stable per-layer random seeds
from fractions import Fraction  # Compare presentation and generation times exactly

import numpy as np  # Create frame buffers and disabled-layer grids
from numpy.typing import NDArray  # Describe NumPy array types

from ca_video.catalogs.rules_3d import getPalette3D  # Resolve isometric face colors
from ca_video.config.models import (  # Read validated project and layer settings
    Layer2DConfig,
    Layer3DConfig,
    LayerConfig,
    ProjectConfig,
)
from ca_video.rendering.fade import FadeState  # Interpolate visual cell and voxel presence
from ca_video.rendering.renderer_2d import Renderer2D, scaledGridSize  # Render and map 2D grids
from ca_video.rendering.renderer_3d import Renderer3D  # Rasterize voxel layers
from ca_video.rendering.renderer_3d_projected import ProjectedRenderer3D  # Project camera-aware voxels
from ca_video.simulation.initialization import initializeGrid  # Build configured starting grids
from ca_video.simulation.initialization_3d import initializeGrid3D  # Build starting voxel grids
from ca_video.simulation.life import OuterTotalisticEngine  # Evolve general B/S/C automata
from ca_video.simulation.life_3d import OuterTotalisticEngine3D  # Evolve 3D automata
from ca_video.simulation.wolfram import WolframEngine  # Evolve scrolling elementary histories
from ca_video.simulation.wolfram_3d import WolframEngine3D  # Evolve extruded elementary histories

SimulationEngine = OuterTotalisticEngine | OuterTotalisticEngine3D | WolframEngine | WolframEngine3D
LayerRenderer = Renderer2D | Renderer3D | ProjectedRenderer3D


# :: INT, STRING -> INT
# Derives a stable per-layer seed without Python's randomized hash function
def stableLayerSeed(masterSeed: int, layerId: str) -> int:
    payload = f"ca-video-v1:{masterSeed}:{layerId}".encode()
    return int.from_bytes(hashlib.blake2b(payload, digest_size=8).digest(), "big") & (2**63 - 1)


# Coordinates independent simulations and ordered alpha composition
class ProjectRuntime:

    # CONSTRUCTOR :: projectConfig, (INT, INT)? -> projectRuntime
    # Creates a deterministic runtime for every configured layer
    def __init__(self, project: ProjectConfig, renderSize: tuple[int, int] | None = None) -> None:
        self._project = project
        self._usesProjectSize = renderSize is None
        self._renderWidth, self._renderHeight = renderSize or (project.output.width, project.output.height)
        self._currentFrameIndex = 0
        self._currentTimeTicks = 0
        self._currentTimebase = 1
        self._engines: dict[str, SimulationEngine] = {}
        self._renderers: dict[str, LayerRenderer] = {}
        self._fadeStates: dict[str, FadeState] = {}
        self.reset()

    #
    # Properties
    #

    # PROPERTY :: VOID -> projectConfig
    # Returns the active project settings
    @property
    def project(self) -> ProjectConfig:
        return self._project

    # PROPERTY :: VOID -> simulationEngine
    # Returns the first layer engine for single-layer compatibility
    @property
    def engine(self) -> SimulationEngine:
        return self._engines[self._project.layer.id]

    # PROPERTY :: VOID -> INT
    # Returns the most recently rendered frame index
    @property
    def currentFrameIndex(self) -> int:
        return self._currentFrameIndex

    # PROPERTY :: VOID -> (INT, INT)
    # Returns the raster size produced by this runtime
    @property
    def renderSize(self) -> tuple[int, int]:
        return self._renderWidth, self._renderHeight

    #
    # Instance Methods
    #

    # :: INT -> simulationEngine
    # Returns the engine for a layer in editor order
    def engineForLayer(self, layerIndex: int) -> SimulationEngine:
        layer = self._project.layers[layerIndex]
        return self._engines[layer.id]

    # :: VOID -> NONE
    # Restores every deterministic initial simulation state
    def reset(self) -> None:
        self._engines = {
            layer.id: self._createEngine(layer)
            for layer in self._project.layers
        }
        self._fadeStates = {
            layer.id: FadeState(self._engines[layer.id].grid)
            for layer in self._project.layers
        }
        self._buildRenderers()
        self._currentFrameIndex = 0
        self._currentTimeTicks = 0
        self._currentTimebase = 1

    # :: projectConfig, BOOL, (INT, INT)? -> rgbFrame
    # Reconfigures appearance while optionally rebuilding simulations
    def updateProject(
        self,
        project: ProjectConfig,
        resetSimulation: bool,
        renderSize: tuple[int, int] | None = None,
    ) -> NDArray[np.uint8]:
        previousProject = self._project
        previousIds = tuple(layer.id for layer in self._project.layers)
        nextIds = tuple(layer.id for layer in project.layers)
        if not resetSimulation and previousIds == nextIds:
            presentationSeconds = self._currentTimeTicks / self._currentTimebase
            for layer in previousProject.layers:
                self._fadeStates[layer.id].rebase(layer.fadeRate, presentationSeconds)
        self._project = project
        if renderSize is not None:
            self._usesProjectSize = False
            self._renderWidth, self._renderHeight = renderSize
        elif self._usesProjectSize:
            self._renderWidth, self._renderHeight = project.output.width, project.output.height
        if resetSimulation or previousIds != nextIds:
            self.reset()
        else:
            self._buildRenderers()
        return self._composite()

    # :: INT -> rgbFrame
    # Advances deterministically to and renders a requested output frame
    def renderFrame(self, frameIndex: int) -> NDArray[np.uint8]:
        return self.renderAtTick(frameIndex, self._project.output.fps)

    # :: INT, INT -> rgbFrame
    # Renders a rational presentation time for preview or export sampling
    def renderAtTick(self, tickIndex: int, ticksPerSecond: int) -> NDArray[np.uint8]:
        if tickIndex < 0:
            raise ValueError("tick index must not be negative")
        if ticksPerSecond < 1:
            raise ValueError("timebase must be positive")
        targetTime = Fraction(tickIndex, ticksPerSecond)
        currentTime = Fraction(self._currentTimeTicks, self._currentTimebase)
        if targetTime < currentTime:
            self.reset()
        for layer in self._project.layers:
            if not layer.enabled:
                continue
            self._advanceLayerTo(layer, targetTime)
        self._currentTimeTicks = tickIndex
        self._currentTimebase = ticksPerSecond
        self._currentFrameIndex = (tickIndex * self._project.output.fps) // ticksPerSecond
        return self._composite()

    # :: VOID -> rgbFrame
    # Advances every enabled layer by exactly one generation
    def stepOnce(self) -> NDArray[np.uint8]:
        frameCandidates = [self._currentFrameIndex]
        transitionSeconds = self._currentTimeTicks / self._currentTimebase
        for layer in self._project.layers:
            if not layer.enabled:
                continue
            engine = self._engines[layer.id]
            engine.step()
            self._fadeStates[layer.id].transition(engine.grid, layer.fadeRate, transitionSeconds)
            numerator = engine.generation * layer.stepIntervalMs * self._project.output.fps
            frameCandidates.append((numerator + 999) // 1000)
        self._currentFrameIndex = max(frameCandidates)
        self._currentTimeTicks = self._currentFrameIndex
        self._currentTimebase = self._project.output.fps
        return self._composite()

    #
    # Protected Methods
    #

    # :: layerConfig -> simulationEngine
    # Creates one deterministically initialized layer engine
    def _createEngine(self, layer: LayerConfig) -> SimulationEngine:
        if isinstance(layer, Layer3DConfig):
            if layer.simulationMode == "wolfram_3d_extruded":
                ruleNumber = layer.wolframRule or 0
                if not layer.enabled:
                    return WolframEngine3D.blank(
                        layer.gridSize,
                        ruleNumber,
                        layer.extrusionDepth,
                        layer.extrusionOffset,
                    )
                initialWolfram = layer.initial
                resolvedWolframSeed = (
                    layer.seed if layer.seed is not None else stableLayerSeed(self._project.seed, layer.id)
                )
                return WolframEngine3D(
                    layer.gridSize,
                    ruleNumber,
                    initialWolfram.type,
                    initialWolfram.density,
                    resolvedWolframSeed,
                    initialWolfram.bits,
                    layer.extrusionDepth,
                    layer.extrusionOffset,
                )
            if layer.rule is None:
                raise ValueError("outer-totalistic 3D layer is missing its rule")
            if not layer.enabled:
                grid3D = np.zeros((layer.gridSize, layer.gridSize, layer.gridSize), dtype=np.uint8)
                return OuterTotalisticEngine3D(grid3D, layer.rule, layer.boundary)
            initial3D = layer.initial
            resolvedSeed3D = layer.seed if layer.seed is not None else stableLayerSeed(self._project.seed, layer.id)
            grid3D = initializeGrid3D(
                layer.gridSize,
                initial3D.type,
                initial3D.density,
                initial3D.radius,
                resolvedSeed3D,
                initial3D.cells,
                initial3D.origin,
                layer.boundary,
                initial3D.offsetCells,
            )
            return OuterTotalisticEngine3D(grid3D, layer.rule, layer.boundary)
        if not layer.enabled:
            if layer.simulationMode == "wolfram_2d":
                return WolframEngine.blank(layer.gridWidth, layer.gridHeight, layer.wolframRule or 0)
            if layer.rule is None:
                raise ValueError("outer-totalistic layer is missing its rule")
            grid = np.zeros((layer.gridHeight, layer.gridWidth), dtype=np.uint8)
            return OuterTotalisticEngine(grid, layer.rule, layer.boundary)
        initial = layer.initial
        resolvedSeed = layer.seed if layer.seed is not None else stableLayerSeed(self._project.seed, layer.id)
        if layer.simulationMode == "wolfram_2d":
            if layer.wolframRule is None:
                raise ValueError("Wolfram layer is missing its rule number")
            return WolframEngine(
                layer.gridWidth,
                layer.gridHeight,
                layer.wolframRule,
                initial.type,
                initial.density,
                resolvedSeed,
                initial.bits,
            )
        if layer.rule is None:
            raise ValueError("outer-totalistic layer is missing its rule")
        rlePath = initial.rlePath
        if rlePath is not None and not rlePath.is_absolute():
            rlePath = self._project.baseDir / rlePath
        grid = initializeGrid(
            layer.gridWidth,
            layer.gridHeight,
            initial.type,
            initial.density,
            initial.radius,
            resolvedSeed,
            initial.size,
            initial.cells,
            initial.origin,
            initial.rleData,
            rlePath,
            layer.boundary,
            self._shapeOffsetCells(layer),
        )
        return OuterTotalisticEngine(grid, layer.rule, layer.boundary)

    # :: layer2DConfig -> (INT, INT)
    # Converts export-pixel shape offsets to the nearest logical cells
    def _shapeOffsetCells(self, layer: Layer2DConfig) -> tuple[int, int]:
        renderWidth, renderHeight = scaledGridSize(
            self._project.output.width,
            self._project.output.height,
            layer.gridWidth,
            layer.gridHeight,
            layer.layout,
        )
        return (
            self._nearestCellOffset(layer.initial.offsetPx[0], layer.gridWidth, renderWidth),
            self._nearestCellOffset(layer.initial.offsetPx[1], layer.gridHeight, renderHeight),
        )

    # :: INT, INT, INT -> INT
    # Rounds a signed pixel displacement to the nearest cell away from zero on ties
    def _nearestCellOffset(self, pixelOffset: int, cellCount: int, pixelCount: int) -> int:
        magnitude = (abs(pixelOffset) * cellCount * 2 + pixelCount) // (pixelCount * 2)
        return -magnitude if pixelOffset < 0 else magnitude

    # :: VOID -> NONE
    # Rebuilds renderers for the current output and layer appearances
    def _buildRenderers(self) -> None:
        renderers: dict[str, LayerRenderer] = {}
        for layer in self._project.layers:
            if isinstance(layer, Layer3DConfig):
                if layer.renderStyle == "projected_voxel":
                    renderers[layer.id] = ProjectedRenderer3D(
                        self._renderWidth,
                        self._renderHeight,
                        getPalette3D(layer.palette),
                        layer.camera or self._project.camera,
                        layer.opacity,
                        layer.voxelScale,
                        layer.surfaceOnly,
                        layer.boundary,
                        layer.colorBy,
                        layer.depthShading,
                        layer.vignette,
                        layer.rule.states if layer.rule is not None else 2,
                    )
                else:
                    renderers[layer.id] = Renderer3D(
                        self._renderWidth,
                        self._renderHeight,
                        getPalette3D(layer.palette),
                        layer.opacity,
                        layer.voxelScale,
                        layer.surfaceOnly,
                        layer.boundary,
                    )
            else:
                renderers[layer.id] = Renderer2D(
                    self._renderWidth,
                    self._renderHeight,
                    self._project.canvasBackground,
                    layer.liveColor,
                    layer.opacity,
                    layer.layout,
                    layer.rule.states if layer.rule is not None else 2,
                )
        self._renderers = renderers

    # :: VOID -> rgbFrame
    # Composites enabled layers by z-index and stable editor order
    def _composite(self) -> NDArray[np.uint8]:
        frame = np.empty((self._renderHeight, self._renderWidth, 3), dtype=np.float32)
        frame[:] = self._project.canvasBackground
        indexedLayers = enumerate(self._project.layers)
        presentationSeconds = self._currentTimeTicks / self._currentTimebase
        for _, layer in sorted(indexedLayers, key=lambda item: (item[1].zIndex, item[0])):
            if not layer.enabled:
                continue
            fadeState = self._fadeStates[layer.id]
            fadeState.sample(self._engines[layer.id].grid, layer.fadeRate, presentationSeconds)
            rendered = self._renderers[layer.id].renderLayer(
                self._engines[layer.id].grid,
                presentationSeconds,
                fadeState.presence if layer.fadeRate > 0 else None,
                fadeState.displayGrid if layer.fadeRate > 0 else None,
            )
            alpha = rendered[..., 3:4]
            frame = frame * (1.0 - alpha) + rendered[..., :3] * alpha
        return frame.clip(0, 255).astype(np.uint8)

    # :: layerConfig, fraction -> NONE
    # Evolves one layer and its visual fade state through exact generation boundaries
    def _advanceLayerTo(
        self,
        layer: LayerConfig,
        targetTime: Fraction,
    ) -> None:
        engine = self._engines[layer.id]
        fadeState = self._fadeStates[layer.id]
        nextGenerationTime = Fraction((engine.generation + 1) * layer.stepIntervalMs, 1000)
        while nextGenerationTime <= targetTime:
            engine.step()
            fadeState.transition(engine.grid, layer.fadeRate, float(nextGenerationTime))
            nextGenerationTime = Fraction((engine.generation + 1) * layer.stepIntervalMs, 1000)
