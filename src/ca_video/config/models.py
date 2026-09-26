from __future__ import annotations  # Enable forward references in type annotations

import json  # Parse and serialize persisted project files
import math  # Validate finite numeric settings and derive grid dimensions
import os  # Atomically replace completed project files
import re  # Validate color and identifier formats
import tempfile  # Create same-directory temporary project files
from collections.abc import Mapping  # Describe unvalidated JSON objects
from decimal import Decimal, InvalidOperation  # Calculate exact output frame counts
from pathlib import Path  # Represent project and output paths
from typing import Any  # Describe values before schema validation

from ca_video.catalogs.rules_2d import getRule  # Resolve named 2D rule presets
from ca_video.catalogs.rules_3d import getPalette3D, getRule3D  # Resolve 3D catalogs
from ca_video.simulation.initialization import parseRle  # Validate inline RLE patterns
from ca_video.simulation.rules import OuterTotalisticRule, parseRule  # Validate B/S/C rules

HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
LAYER_ID = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
ENCODER_PRESETS = {
    "ultrafast",
    "superfast",
    "veryfast",
    "faster",
    "fast",
    "medium",
    "slow",
    "slower",
    "veryslow",
}
INITIAL_TYPES = {"random", "center_block", "disc", "cells", "rle", "catalog_default"}
WOLFRAM_INITIAL_TYPES = {"single_center", "random", "bits"}
INITIAL_TYPES_3D = {"random", "center_block", "sphere", "cells", "single", "cross", "catalog_default"}
PROJECTED_COLOR_MODES = {"fixed", "state", "height", "distance"}


# Indicates that a project configuration is invalid or unsupported
class ConfigError(ValueError):
    pass


# :: ANY, STRING -> ARRAY<STRING, ANY>
# Requires a mapping value at the supplied project path
def _asMapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ConfigError(f"{path} must be an object")
    return value


# :: ARRAY<STRING, ANY>, [STRING], STRING -> NONE
# Rejects unrecognized fields in a configuration object
def _rejectUnknown(value: Mapping[str, Any], allowed: set[str], path: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        joined = ", ".join(unknown)
        raise ConfigError(f"{path} contains unsupported field(s): {joined}")


# :: ANY, STRING, INT, INT -> INT
# Validates and returns an integer setting
def _asInteger(value: Any, path: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{path} must be an integer")
    if not minimum <= value <= maximum:
        raise ConfigError(f"{path} must be between {minimum} and {maximum}")
    return value


# :: ANY, STRING, FLOAT, FLOAT -> FLOAT
# Validates and returns a finite numeric setting
def _asNumber(value: Any, path: str, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{path} must be a number")
    result = float(value)
    if not math.isfinite(result) or not minimum <= result <= maximum:
        raise ConfigError(f"{path} must be between {minimum} and {maximum}")
    return result


# :: ANY, STRING -> (INT, INT, INT)
# Parses a color written in #RRGGBB form
def _asColor(value: Any, path: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or not HEX_COLOR.fullmatch(value):
        raise ConfigError(f"{path} must be a color in #RRGGBB form")
    return tuple(int(value[index : index + 2], 16) for index in (1, 3, 5))


# :: (INT, INT, INT) -> STRING
# Converts an RGB tuple to normalized #RRGGBB form
def colorToHex(color: tuple[int, int, int]) -> str:
    return "#" + "".join(f"{channel:02x}" for channel in color)


# Stores validated video output settings
class OutputConfig:

    # CONSTRUCTOR :: path, INT, INT, INT, FLOAT, INT, STRING -> outputConfig
    # Creates immutable-by-convention output settings
    def __init__(
        self,
        path: Path,
        width: int,
        height: int,
        fps: int,
        durationSeconds: float,
        crf: int = 18,
        encoderPreset: str = "medium",
    ) -> None:
        self._path = path
        self._width = width
        self._height = height
        self._fps = fps
        self._durationSeconds = durationSeconds
        self._crf = crf
        self._encoderPreset = encoderPreset

    #
    # Properties
    #

    # PROPERTY :: VOID -> path
    # Returns the configured output path
    @property
    def path(self) -> Path:
        return self._path

    # PROPERTY :: VOID -> INT
    # Returns the output width in pixels
    @property
    def width(self) -> int:
        return self._width

    # PROPERTY :: VOID -> INT
    # Returns the output height in pixels
    @property
    def height(self) -> int:
        return self._height

    # PROPERTY :: VOID -> INT
    # Returns the output frame rate
    @property
    def fps(self) -> int:
        return self._fps

    # PROPERTY :: VOID -> FLOAT
    # Returns the output duration in seconds
    @property
    def durationSeconds(self) -> float:
        return self._durationSeconds

    # PROPERTY :: VOID -> INT
    # Returns the H.264 constant-rate factor
    @property
    def crf(self) -> int:
        return self._crf

    # PROPERTY :: VOID -> STRING
    # Returns the FFmpeg encoder speed preset
    @property
    def encoderPreset(self) -> str:
        return self._encoderPreset

    # PROPERTY :: VOID -> INT
    # Returns the exact number of frames in the output
    @property
    def totalFrames(self) -> int:
        try:
            frameCount = Decimal(str(self._durationSeconds)) * self._fps
        except InvalidOperation as error:
            raise ConfigError("output.duration_seconds is invalid") from error
        integral = frameCount.to_integral_value()
        if abs(frameCount - integral) > Decimal("0.000001"):
            raise ConfigError("output.duration_seconds * output.fps must be an integer")
        return int(integral)

    #
    # Instance Methods
    #

    # :: path?, INT?, INT?, INT?, FLOAT?, STRING? -> outputConfig
    # Returns a copy with selected values replaced
    def withOverrides(
        self,
        *,
        path: Path | None = None,
        width: int | None = None,
        height: int | None = None,
        fps: int | None = None,
        durationSeconds: float | None = None,
        encoderPreset: str | None = None,
    ) -> OutputConfig:
        return OutputConfig(
            path if path is not None else self._path,
            width if width is not None else self._width,
            height if height is not None else self._height,
            fps if fps is not None else self._fps,
            durationSeconds if durationSeconds is not None else self._durationSeconds,
            self._crf,
            encoderPreset if encoderPreset is not None else self._encoderPreset,
        )


# Stores validated settings for a two-dimensional initializer
class Initial2DConfig:

    # CONSTRUCTOR :: STRING, FLOAT, INT, (INT, INT)?, ((INT, INT)), STRING, STRING?, path?, (INT), (INT, INT) -> initial2DConfig
    # Creates immutable-by-convention initializer settings
    def __init__(
        self,
        type: str,
        density: float = 1,
        radius: int = 2,
        size: tuple[int, int] | None = None,
        cells: tuple[tuple[int, int], ...] = (),
        origin: str = "center",
        rleData: str | None = None,
        rlePath: Path | None = None,
        bits: tuple[int, ...] = (),
        offsetPx: tuple[int, int] = (0, 0),
    ) -> None:
        self._type = type
        self._density = density
        self._radius = radius
        self._size = size
        self._cells = cells
        self._origin = origin
        self._rleData = rleData
        self._rlePath = rlePath
        self._bits = bits
        self._offsetPx = offsetPx

    #
    # Properties
    #

    # PROPERTY :: VOID -> STRING
    # Returns the initializer type
    @property
    def type(self) -> str:
        return self._type

    # PROPERTY :: VOID -> FLOAT
    # Returns the fill density used by geometric initializers
    @property
    def density(self) -> float:
        return self._density

    # PROPERTY :: VOID -> INT
    # Returns the shape radius
    @property
    def radius(self) -> int:
        return self._radius

    # PROPERTY :: VOID -> (INT, INT)?
    # Returns an explicit block size when configured
    @property
    def size(self) -> tuple[int, int] | None:
        return self._size

    # PROPERTY :: VOID -> ((INT, INT))
    # Returns explicit initial cell coordinates
    @property
    def cells(self) -> tuple[tuple[int, int], ...]:
        return self._cells

    # PROPERTY :: VOID -> STRING
    # Returns whether explicit coordinates are absolute or centered
    @property
    def origin(self) -> str:
        return self._origin

    # PROPERTY :: VOID -> STRING?
    # Returns inline RLE data
    @property
    def rleData(self) -> str | None:
        return self._rleData

    # PROPERTY :: VOID -> path?
    # Returns a project-relative RLE path
    @property
    def rlePath(self) -> Path | None:
        return self._rlePath

    # PROPERTY :: VOID -> (INT)
    # Returns the explicit centered Wolfram starting pattern
    @property
    def bits(self) -> tuple[int, ...]:
        return self._bits

    # PROPERTY :: VOID -> (INT, INT)
    # Returns the geometric center offset in export pixels
    @property
    def offsetPx(self) -> tuple[int, int]:
        return self._offsetPx


# Stores validated settings for an outer-totalistic or Wolfram 2D layer
class Layer2DConfig:

    # CONSTRUCTOR :: STRING, STRING, BOOL, INT, FLOAT, INT, INT, INT, STRING, FLOAT, (INT, INT, INT), STRING, outerTotalisticRule?, STRING?, initial2DConfig?, INT?, INT?, STRING, INT? -> layer2DConfig
    # Creates immutable-by-convention 2D layer settings
    def __init__(
        self,
        id: str,
        name: str,
        enabled: bool,
        zIndex: int,
        opacity: float,
        stepIntervalMs: int,
        gridWidth: int,
        gridHeight: int,
        boundary: str,
        initialDensity: float,
        liveColor: tuple[int, int, int],
        layout: str,
        rule: OuterTotalisticRule | None = None,
        rulePreset: str | None = "life",
        initial: Initial2DConfig | None = None,
        seed: int | None = None,
        cellSizePx: int | None = None,
        simulationMode: str = "outer_totalistic",
        wolframRule: int | None = None,
    ) -> None:
        self._id = id
        self._name = name
        self._enabled = enabled
        self._zIndex = zIndex
        self._opacity = opacity
        self._stepIntervalMs = stepIntervalMs
        self._gridWidth = gridWidth
        self._gridHeight = gridHeight
        self._boundary = boundary
        self._initialDensity = initialDensity
        self._liveColor = liveColor
        self._layout = layout
        self._rule = rule if simulationMode == "wolfram_2d" else (rule or parseRule("B3/S23"))
        self._rulePreset = rulePreset
        self._initial = initial or Initial2DConfig("random", initialDensity)
        self._seed = seed
        self._cellSizePx = cellSizePx
        self._simulationMode = simulationMode
        self._wolframRule = wolframRule

    #
    # Properties
    #

    # PROPERTY :: VOID -> STRING
    # Returns the layer dimensionality
    @property
    def dimension(self) -> str:
        return "2d"

    # PROPERTY :: VOID -> STRING
    # Returns the stable layer identifier
    @property
    def id(self) -> str:
        return self._id

    # PROPERTY :: VOID -> STRING
    # Returns the display name
    @property
    def name(self) -> str:
        return self._name

    # PROPERTY :: VOID -> BOOL
    # Returns whether the layer is active
    @property
    def enabled(self) -> bool:
        return self._enabled

    # PROPERTY :: VOID -> INT
    # Returns the visual stacking index
    @property
    def zIndex(self) -> int:
        return self._zIndex

    # PROPERTY :: VOID -> FLOAT
    # Returns layer opacity
    @property
    def opacity(self) -> float:
        return self._opacity

    # PROPERTY :: VOID -> INT
    # Returns milliseconds between simulation generations
    @property
    def stepIntervalMs(self) -> int:
        return self._stepIntervalMs

    # PROPERTY :: VOID -> INT
    # Returns grid width in cells
    @property
    def gridWidth(self) -> int:
        return self._gridWidth

    # PROPERTY :: VOID -> INT
    # Returns grid height in cells
    @property
    def gridHeight(self) -> int:
        return self._gridHeight

    # PROPERTY :: VOID -> STRING
    # Returns the boundary mode
    @property
    def boundary(self) -> str:
        return self._boundary

    # PROPERTY :: VOID -> FLOAT
    # Returns initial live-cell density
    @property
    def initialDensity(self) -> float:
        return self._initialDensity

    # PROPERTY :: VOID -> (INT, INT, INT)
    # Returns the live-cell RGB color
    @property
    def liveColor(self) -> tuple[int, int, int]:
        return self._liveColor

    # PROPERTY :: VOID -> STRING
    # Returns the fit or cover layout mode
    @property
    def layout(self) -> str:
        return self._layout

    # PROPERTY :: VOID -> outerTotalisticRule?
    # Returns the parsed simulation rule
    @property
    def rule(self) -> OuterTotalisticRule | None:
        return self._rule

    # PROPERTY :: VOID -> STRING?
    # Returns the catalog key or None for a custom rule
    @property
    def rulePreset(self) -> str | None:
        return self._rulePreset

    # PROPERTY :: VOID -> initial2DConfig
    # Returns initial-condition settings
    @property
    def initial(self) -> Initial2DConfig:
        return self._initial

    # PROPERTY :: VOID -> INT?
    # Returns the explicit layer seed or None when it is derived
    @property
    def seed(self) -> int | None:
        return self._seed

    # PROPERTY :: VOID -> INT?
    # Returns the export-relative cell size when the grid is derived
    @property
    def cellSizePx(self) -> int | None:
        return self._cellSizePx

    # PROPERTY :: VOID -> STRING
    # Returns the selected two-dimensional simulation family
    @property
    def simulationMode(self) -> str:
        return self._simulationMode

    # PROPERTY :: VOID -> INT?
    # Returns the elementary rule number for a Wolfram layer
    @property
    def wolframRule(self) -> int | None:
        return self._wolframRule


# Stores validated settings for a three-dimensional initializer
class Initial3DConfig:

    # CONSTRUCTOR :: STRING, FLOAT, INT, ((INT, INT, INT)), STRING, (INT), (INT, INT, INT) -> initial3DConfig
    # Creates immutable-by-convention voxel initialization settings
    def __init__(
        self,
        type: str,
        density: float = 1,
        radius: int = 2,
        cells: tuple[tuple[int, int, int], ...] = (),
        origin: str = "center",
        bits: tuple[int, ...] = (),
        offsetCells: tuple[int, int, int] = (0, 0, 0),
    ) -> None:
        self._type = type
        self._density = density
        self._radius = radius
        self._cells = cells
        self._origin = origin
        self._bits = bits
        self._offsetCells = offsetCells

    # PROPERTY :: VOID -> STRING
    # Returns the initializer type
    @property
    def type(self) -> str:
        return self._type

    # PROPERTY :: VOID -> FLOAT
    # Returns the shape fill density
    @property
    def density(self) -> float:
        return self._density

    # PROPERTY :: VOID -> INT
    # Returns the sphere or block radius
    @property
    def radius(self) -> int:
        return self._radius

    # PROPERTY :: VOID -> ((INT, INT, INT))
    # Returns explicit voxel coordinates
    @property
    def cells(self) -> tuple[tuple[int, int, int], ...]:
        return self._cells

    # PROPERTY :: VOID -> STRING
    # Returns whether explicit coordinates are absolute or centered
    @property
    def origin(self) -> str:
        return self._origin

    # PROPERTY :: VOID -> (INT)
    # Returns an explicit centered Wolfram source row
    @property
    def bits(self) -> tuple[int, ...]:
        return self._bits

    # PROPERTY :: VOID -> (INT, INT, INT)
    # Returns the geometric seed displacement from grid center
    @property
    def offsetCells(self) -> tuple[int, int, int]:
        return self._offsetCells


# Stores deterministic camera settings for projected voxel rendering
class CameraConfig:

    # CONSTRUCTOR :: STRING, FLOAT, FLOAT, FLOAT, FLOAT, FLOAT, FLOAT, FLOAT -> cameraConfig
    # Creates immutable-by-convention camera settings
    def __init__(
        self,
        projection: str = "perspective",
        azimuthDeg: float = 30,
        elevationDeg: float = 28,
        zoom: float = 1,
        perspectiveStrength: float = 0.35,
        rotationDegPerSecond: float = 12,
        panX: float = 0,
        panY: float = 0,
    ) -> None:
        self._projection = projection
        self._azimuthDeg = azimuthDeg
        self._elevationDeg = elevationDeg
        self._zoom = zoom
        self._perspectiveStrength = perspectiveStrength
        self._rotationDegPerSecond = rotationDegPerSecond
        self._panX = panX
        self._panY = panY

    # PROPERTY :: VOID -> STRING
    # Returns perspective or orthographic projection
    @property
    def projection(self) -> str:
        return self._projection

    # PROPERTY :: VOID -> FLOAT
    # Returns the base rotation around the vertical axis
    @property
    def azimuthDeg(self) -> float:
        return self._azimuthDeg

    # PROPERTY :: VOID -> FLOAT
    # Returns the camera elevation angle
    @property
    def elevationDeg(self) -> float:
        return self._elevationDeg

    # PROPERTY :: VOID -> FLOAT
    # Returns the camera zoom multiplier
    @property
    def zoom(self) -> float:
        return self._zoom

    # PROPERTY :: VOID -> FLOAT
    # Returns the perspective distortion strength
    @property
    def perspectiveStrength(self) -> float:
        return self._perspectiveStrength

    # PROPERTY :: VOID -> FLOAT
    # Returns the time-based azimuth rotation rate
    @property
    def rotationDegPerSecond(self) -> float:
        return self._rotationDegPerSecond

    # PROPERTY :: VOID -> FLOAT
    # Returns horizontal pan in normalized canvas units
    @property
    def panX(self) -> float:
        return self._panX

    # PROPERTY :: VOID -> FLOAT
    # Returns vertical pan in normalized canvas units
    @property
    def panY(self) -> float:
        return self._panY


# Stores validated settings for a three-dimensional voxel layer
class Layer3DConfig:

    # CONSTRUCTOR :: STRING, STRING, BOOL, INT, FLOAT, INT, INT, STRING, outerTotalisticRule?, STRING?, initial3DConfig, INT?, STRING, INT, BOOL, STRING, STRING, BOOL, BOOL, cameraConfig?, STRING, INT?, INT, INT -> layer3DConfig
    # Creates immutable-by-convention 3D layer settings
    def __init__(
        self,
        id: str,
        name: str,
        enabled: bool,
        zIndex: int,
        opacity: float,
        stepIntervalMs: int,
        gridSize: int,
        boundary: str,
        rule: OuterTotalisticRule | None,
        rulePreset: str | None,
        initial: Initial3DConfig,
        seed: int | None,
        palette: str,
        voxelScale: int,
        surfaceOnly: bool,
        renderStyle: str = "isometric_voxel",
        colorBy: str = "fixed",
        depthShading: bool = True,
        vignette: bool = False,
        camera: CameraConfig | None = None,
        simulationMode: str = "outer_totalistic",
        wolframRule: int | None = None,
        extrusionDepth: int = 1,
        extrusionOffset: int = 0,
    ) -> None:
        self._id = id
        self._name = name
        self._enabled = enabled
        self._zIndex = zIndex
        self._opacity = opacity
        self._stepIntervalMs = stepIntervalMs
        self._gridSize = gridSize
        self._boundary = boundary
        self._rule = rule
        self._rulePreset = rulePreset
        self._initial = initial
        self._seed = seed
        self._palette = palette
        self._voxelScale = voxelScale
        self._surfaceOnly = surfaceOnly
        self._renderStyle = renderStyle
        self._colorBy = colorBy
        self._depthShading = depthShading
        self._vignette = vignette
        self._camera = camera
        self._simulationMode = simulationMode
        self._wolframRule = wolframRule
        self._extrusionDepth = extrusionDepth
        self._extrusionOffset = extrusionOffset

    # PROPERTY :: VOID -> STRING
    # Returns the layer dimensionality
    @property
    def dimension(self) -> str:
        return "3d"

    # PROPERTY :: VOID -> STRING
    # Returns the stable layer identifier
    @property
    def id(self) -> str:
        return self._id

    # PROPERTY :: VOID -> STRING
    # Returns the display name
    @property
    def name(self) -> str:
        return self._name

    # PROPERTY :: VOID -> BOOL
    # Returns whether the layer is active
    @property
    def enabled(self) -> bool:
        return self._enabled

    # PROPERTY :: VOID -> INT
    # Returns the visual stacking index
    @property
    def zIndex(self) -> int:
        return self._zIndex

    # PROPERTY :: VOID -> FLOAT
    # Returns layer opacity
    @property
    def opacity(self) -> float:
        return self._opacity

    # PROPERTY :: VOID -> INT
    # Returns milliseconds between generations
    @property
    def stepIntervalMs(self) -> int:
        return self._stepIntervalMs

    # PROPERTY :: VOID -> INT
    # Returns the cubic grid axis length
    @property
    def gridSize(self) -> int:
        return self._gridSize

    # PROPERTY :: VOID -> STRING
    # Returns the boundary mode
    @property
    def boundary(self) -> str:
        return self._boundary

    # PROPERTY :: VOID -> outerTotalisticRule?
    # Returns the parsed 3D rule for an outer-totalistic layer
    @property
    def rule(self) -> OuterTotalisticRule | None:
        return self._rule

    # PROPERTY :: VOID -> STRING?
    # Returns the 3D catalog rule key for an outer-totalistic layer
    @property
    def rulePreset(self) -> str | None:
        return self._rulePreset

    # PROPERTY :: VOID -> initial3DConfig
    # Returns the voxel initializer
    @property
    def initial(self) -> Initial3DConfig:
        return self._initial

    # PROPERTY :: VOID -> INT?
    # Returns the explicit layer seed or None when derived
    @property
    def seed(self) -> int | None:
        return self._seed

    # PROPERTY :: VOID -> STRING
    # Returns the isometric face palette key
    @property
    def palette(self) -> str:
        return self._palette

    # PROPERTY :: VOID -> INT
    # Returns zero for automatic sizing or a fixed half-width in pixels
    @property
    def voxelScale(self) -> int:
        return self._voxelScale

    # PROPERTY :: VOID -> BOOL
    # Returns whether hidden interior voxels are culled
    @property
    def surfaceOnly(self) -> bool:
        return self._surfaceOnly

    # PROPERTY :: VOID -> STRING
    # Returns the selected 3D rasterization style
    @property
    def renderStyle(self) -> str:
        return self._renderStyle

    # PROPERTY :: VOID -> STRING
    # Returns the projected voxel color mapping
    @property
    def colorBy(self) -> str:
        return self._colorBy

    # PROPERTY :: VOID -> BOOL
    # Returns whether projected voxels are depth shaded
    @property
    def depthShading(self) -> bool:
        return self._depthShading

    # PROPERTY :: VOID -> BOOL
    # Returns whether the projected layer darkens canvas edges
    @property
    def vignette(self) -> bool:
        return self._vignette

    # PROPERTY :: VOID -> cameraConfig?
    # Returns a layer camera override or None for the project camera
    @property
    def camera(self) -> CameraConfig | None:
        return self._camera

    # PROPERTY :: VOID -> STRING
    # Returns the selected three-dimensional simulation family
    @property
    def simulationMode(self) -> str:
        return self._simulationMode

    # PROPERTY :: VOID -> INT?
    # Returns the elementary rule number for an extruded Wolfram layer
    @property
    def wolframRule(self) -> int | None:
        return self._wolframRule

    # PROPERTY :: VOID -> INT
    # Returns the centered Wolfram extrusion thickness
    @property
    def extrusionDepth(self) -> int:
        return self._extrusionDepth

    # PROPERTY :: VOID -> INT
    # Returns the Wolfram depth-band displacement from grid center
    @property
    def extrusionOffset(self) -> int:
        return self._extrusionOffset


LayerConfig = Layer2DConfig | Layer3DConfig


# Stores a fully validated project configuration
class ProjectConfig:

    # CONSTRUCTOR :: INT, STRING, INT, outputConfig, (INT, INT, INT), layerConfig|(layerConfig), path, cameraConfig? -> projectConfig
    # Creates immutable-by-convention project settings
    def __init__(
        self,
        schemaVersion: int,
        name: str,
        seed: int,
        output: OutputConfig,
        canvasBackground: tuple[int, int, int],
        layers: LayerConfig | tuple[LayerConfig, ...] | list[LayerConfig],
        baseDir: Path,
        camera: CameraConfig | None = None,
    ) -> None:
        self._schemaVersion = schemaVersion
        self._name = name
        self._seed = seed
        self._output = output
        self._canvasBackground = canvasBackground
        self._layers = (layers,) if isinstance(layers, (Layer2DConfig, Layer3DConfig)) else tuple(layers)
        if not self._layers:
            raise ConfigError("a project requires at least one layer")
        self._baseDir = baseDir
        self._camera = camera or CameraConfig()

    #
    # Properties
    #

    # PROPERTY :: VOID -> INT
    # Returns the project schema version
    @property
    def schemaVersion(self) -> int:
        return self._schemaVersion

    # PROPERTY :: VOID -> STRING
    # Returns the project name
    @property
    def name(self) -> str:
        return self._name

    # PROPERTY :: VOID -> INT
    # Returns the deterministic master seed
    @property
    def seed(self) -> int:
        return self._seed

    # PROPERTY :: VOID -> outputConfig
    # Returns output settings
    @property
    def output(self) -> OutputConfig:
        return self._output

    # PROPERTY :: VOID -> (INT, INT, INT)
    # Returns the canvas background color
    @property
    def canvasBackground(self) -> tuple[int, int, int]:
        return self._canvasBackground

    # PROPERTY :: VOID -> layerConfig
    # Returns the configured layer
    @property
    def layer(self) -> LayerConfig:
        return self._layers[0]

    # PROPERTY :: VOID -> (layerConfig)
    # Returns all configured layers in editor order
    @property
    def layers(self) -> tuple[LayerConfig, ...]:
        return self._layers

    # PROPERTY :: VOID -> path
    # Returns the project-relative base directory
    @property
    def baseDir(self) -> Path:
        return self._baseDir

    # PROPERTY :: VOID -> cameraConfig
    # Returns the project camera used by projected layers without overrides
    @property
    def camera(self) -> CameraConfig:
        return self._camera

    #
    # Instance Methods
    #

    # :: VOID -> path
    # Resolves the configured output path against the project directory
    def outputPath(self) -> Path:
        path = self._output.path
        return path if path.is_absolute() else self._baseDir / path

    # :: path -> projectConfig
    # Returns a project copy with a different output path
    def withOutputPath(self, path: Path) -> ProjectConfig:
        return ProjectConfig(
            self._schemaVersion,
            self._name,
            self._seed,
            self._output.withOverrides(path=path),
            self._canvasBackground,
            self._layers,
            self._baseDir,
            self._camera,
        )

    # :: VOID -> ARRAY<STRING, ANY>
    # Serializes the normalized project schema
    def toDict(self) -> dict[str, Any]:
        return {
            "schema_version": self._schemaVersion,
            "project": {"name": self._name, "seed": self._seed},
            "output": {
                "path": str(self._output.path),
                "width": self._output.width,
                "height": self._output.height,
                "fps": self._output.fps,
                "duration_seconds": self._output.durationSeconds,
                "codec": "h264",
                "crf": self._output.crf,
                "encoder_preset": self._output.encoderPreset,
            },
            "canvas": {"background": colorToHex(self._canvasBackground)},
            "camera": _cameraToDict(self._camera),
            "layers": [_layerToDict(layer) for layer in self._layers],
        }


# :: cameraConfig -> ARRAY<STRING, ANY>
# Serializes normalized projected-camera settings
def _cameraToDict(camera: CameraConfig) -> dict[str, Any]:
    return {
        "projection": camera.projection,
        "azimuth_deg": camera.azimuthDeg,
        "elevation_deg": camera.elevationDeg,
        "zoom": camera.zoom,
        "perspective_strength": camera.perspectiveStrength,
        "rotation_deg_per_second": camera.rotationDegPerSecond,
        "pan_x": camera.panX,
        "pan_y": camera.panY,
    }


# :: layerConfig -> ARRAY<STRING, ANY>
# Serializes one normalized layer
def _layerToDict(layer: LayerConfig) -> dict[str, Any]:
    if isinstance(layer, Layer3DConfig):
        initial = layer.initial
        initialData: dict[str, Any] = {"type": initial.type}
        if initial.type in {"random", "center_block", "sphere"}:
            initialData["density"] = initial.density
        if initial.type in {"center_block", "sphere"}:
            initialData["radius"] = initial.radius
        if initial.type in {"center_block", "sphere", "single", "cross"} and initial.offsetCells != (0, 0, 0):
            initialData["offset_cells"] = list(initial.offsetCells)
        if initial.type == "cells":
            initialData["origin"] = initial.origin
            initialData["cells"] = [list(cell) for cell in initial.cells]
        if initial.type == "bits":
            initialData["bits"] = list(initial.bits)
        renderData: dict[str, Any] = {
            "style": layer.renderStyle,
            "palette": layer.palette,
            "voxel_scale": layer.voxelScale or "auto",
            "surface_only": layer.surfaceOnly,
        }
        if layer.renderStyle == "projected_voxel":
            renderData.update(
                {
                    "color_by": layer.colorBy,
                    "depth_shading": layer.depthShading,
                    "vignette": layer.vignette,
                }
            )
            if layer.camera is not None:
                renderData["camera"] = _cameraToDict(layer.camera)
        simulationData: dict[str, Any] = {
            "mode": layer.simulationMode,
            "grid": {"grid_size": layer.gridSize, "boundary": layer.boundary},
            "rule": (
                {"number": layer.wolframRule}
                if layer.simulationMode == "wolfram_3d_extruded"
                else {"preset": layer.rulePreset}
            ),
            "initial": initialData,
        }
        if layer.simulationMode == "wolfram_3d_extruded":
            simulationData["extrusion_depth"] = layer.extrusionDepth
            if layer.extrusionOffset:
                simulationData["extrusion_offset"] = layer.extrusionOffset
        return {
            "id": layer.id,
            "name": layer.name,
            **({"seed": layer.seed} if layer.seed is not None else {}),
            "enabled": layer.enabled,
            "dimension": "3d",
            "z_index": layer.zIndex,
            "opacity": layer.opacity,
            "step_interval_ms": layer.stepIntervalMs,
            "simulation": simulationData,
            "render": renderData,
        }

    initial = layer.initial
    initialData: dict[str, Any] = {"type": initial.type}
    if layer.simulationMode == "wolfram_2d":
        if initial.type == "random":
            initialData["density"] = initial.density
        if initial.type == "bits":
            initialData["bits"] = list(initial.bits)
        ruleData = {"number": layer.wolframRule}
    else:
        if initial.type in {"random", "center_block", "disc"}:
            initialData["density"] = initial.density
        if initial.type in {"center_block", "disc"}:
            if initial.offsetPx != (0, 0):
                initialData["offset_px"] = list(initial.offsetPx)
            if initial.size is not None and initial.type == "center_block":
                initialData["size"] = list(initial.size)
            else:
                initialData["radius"] = initial.radius
        if initial.type == "cells":
            initialData["origin"] = initial.origin
            initialData["cells"] = [list(cell) for cell in initial.cells]
        if initial.type == "rle":
            initialData["origin"] = initial.origin
            if initial.rleData is not None:
                initialData["data"] = initial.rleData
            elif initial.rlePath is not None:
                initialData["path"] = str(initial.rlePath)
        if layer.rule is None:
            raise ConfigError("outer-totalistic layer is missing its rule")
        ruleData = (
            {"preset": layer.rulePreset}
            if layer.rulePreset is not None
            else {"notation": layer.rule.notation, "neighborhood": layer.rule.neighborhood}
        )
    return {
        "id": layer.id,
        "name": layer.name,
        **({"seed": layer.seed} if layer.seed is not None else {}),
        "enabled": layer.enabled,
        "dimension": "2d",
        "z_index": layer.zIndex,
        "opacity": layer.opacity,
        "step_interval_ms": layer.stepIntervalMs,
        "simulation": {
            "mode": layer.simulationMode,
            "grid": {
                **(
                    {"cell_size_px": layer.cellSizePx}
                    if layer.cellSizePx is not None
                    else {"size": [layer.gridWidth, layer.gridHeight]}
                ),
                "boundary": layer.boundary,
            },
            "rule": ruleData,
            "initial": initialData,
        },
        "render": {
            "style": "cells",
            "color": colorToHex(layer.liveColor),
            "layout": layer.layout,
        },
    }


# :: ANY, STRING, cameraConfig? -> cameraConfig
# Parses complete or partial projected camera settings
def _parseCamera(value: Any, path: str, base: CameraConfig | None = None) -> CameraConfig:
    data = _asMapping(value, path)
    _rejectUnknown(
        data,
        {
            "projection",
            "azimuth_deg",
            "elevation_deg",
            "zoom",
            "perspective_strength",
            "rotation_deg_per_second",
            "pan_x",
            "pan_y",
        },
        path,
    )
    defaults = base or CameraConfig()
    projection = data.get("projection", defaults.projection)
    if projection not in {"orthographic", "perspective"}:
        raise ConfigError(f"{path}.projection must be orthographic or perspective")
    return CameraConfig(
        projection,
        _asNumber(data.get("azimuth_deg", defaults.azimuthDeg), f"{path}.azimuth_deg", -360, 360),
        _asNumber(data.get("elevation_deg", defaults.elevationDeg), f"{path}.elevation_deg", -89, 89),
        _asNumber(data.get("zoom", defaults.zoom), f"{path}.zoom", 0.1, 10),
        _asNumber(
            data.get("perspective_strength", defaults.perspectiveStrength),
            f"{path}.perspective_strength",
            0,
            1,
        ),
        _asNumber(
            data.get("rotation_deg_per_second", defaults.rotationDegPerSecond),
            f"{path}.rotation_deg_per_second",
            -360,
            360,
        ),
        _asNumber(data.get("pan_x", defaults.panX), f"{path}.pan_x", -1, 1),
        _asNumber(data.get("pan_y", defaults.panY), f"{path}.pan_y", -1, 1),
    )


# :: ARRAY<STRING, ANY>, STRING, STRING, BOOL, INT, FLOAT, INT, INT?, cameraConfig -> layer3DConfig
# Parses a validated common layer envelope as a 3D voxel layer
def _parseLayer3D(
    layerData: Mapping[str, Any],
    layerId: str,
    layerName: str,
    enabled: bool,
    zIndex: int,
    opacity: float,
    stepIntervalMs: int,
    layerSeed: int | None,
    projectCamera: CameraConfig,
) -> Layer3DConfig:
    simulation = _asMapping(layerData.get("simulation"), "layers[0].simulation")
    _rejectUnknown(
        simulation,
        {"mode", "grid", "rule", "initial", "extrusion_depth", "extrusion_offset"},
        "layers[0].simulation",
    )
    simulationMode = simulation.get("mode")
    if simulationMode not in {"outer_totalistic", "wolfram_3d_extruded"}:
        raise ConfigError("3D simulation mode must be outer_totalistic or wolfram_3d_extruded")

    grid = _asMapping(simulation.get("grid"), "layers[0].simulation.grid")
    _rejectUnknown(grid, {"grid_size", "boundary"}, "layers[0].simulation.grid")
    gridSize = _asInteger(grid.get("grid_size"), "layers[0].simulation.grid.grid_size", 8, 80)
    boundary = grid.get("boundary", "fixed")
    if boundary not in {"wrap", "fixed"}:
        raise ConfigError("layers[0].simulation.grid.boundary must be wrap or fixed")
    if simulationMode == "wolfram_3d_extruded" and boundary != "fixed":
        raise ConfigError("Wolfram 3D extrusion requires a fixed volume boundary")

    ruleData = _asMapping(simulation.get("rule"), "layers[0].simulation.rule")
    initialData = _asMapping(simulation.get("initial"), "layers[0].simulation.initial")
    wolframRule: int | None = None
    extrusionDepth = max(1, gridSize // 4)
    extrusionOffset = 0
    if simulationMode == "wolfram_3d_extruded":
        _rejectUnknown(ruleData, {"number"}, "layers[0].simulation.rule")
        wolframRule = _asInteger(ruleData.get("number"), "layers[0].simulation.rule.number", 0, 255)
        parsedRule: OuterTotalisticRule | None = None
        rulePreset: str | None = None
        extrusionDepth = _asInteger(
            simulation.get("extrusion_depth", extrusionDepth),
            "layers[0].simulation.extrusion_depth",
            1,
            gridSize,
        )
        extrusionOffset = _asInteger(
            simulation.get("extrusion_offset", 0),
            "layers[0].simulation.extrusion_offset",
            -gridSize,
            gridSize,
        )
        _rejectUnknown(initialData, {"type", "density", "bits"}, "layers[0].simulation.initial")
        initialType = initialData.get("type")
        if initialType not in WOLFRAM_INITIAL_TYPES:
            choices = ", ".join(sorted(WOLFRAM_INITIAL_TYPES))
            raise ConfigError(f"layers[0].simulation.initial.type must be one of {choices}")
        density = _asNumber(
            initialData.get("density", 0.5),
            "layers[0].simulation.initial.density",
            0,
            1,
        )
        bits: tuple[int, ...] = ()
        if initialType == "bits":
            bitValues = initialData.get("bits")
            if not isinstance(bitValues, list) or not bitValues:
                raise ConfigError("layers[0].simulation.initial.bits must be a non-empty list")
            if len(bitValues) > gridSize:
                raise ConfigError("layers[0].simulation.initial.bits is wider than the grid")
            bits = tuple(
                _asInteger(bit, f"layers[0].simulation.initial.bits[{index}]", 0, 1)
                for index, bit in enumerate(bitValues)
            )
        initial = Initial3DConfig(initialType, density, bits=bits)
    else:
        if "extrusion_depth" in simulation or "extrusion_offset" in simulation:
            raise ConfigError("extrusion controls are supported only for wolfram_3d_extruded")
        _rejectUnknown(ruleData, {"preset"}, "layers[0].simulation.rule")
        rulePreset = ruleData.get("preset")
        if not isinstance(rulePreset, str):
            raise ConfigError("layers[0].simulation.rule.preset must be a string")
        try:
            catalogRule = getRule3D(rulePreset)
            parsedRule = catalogRule.rule
        except (KeyError, ValueError) as error:
            raise ConfigError(str(error)) from error
        _rejectUnknown(
            initialData,
            {"type", "density", "radius", "cells", "origin", "offset_cells"},
            "layers[0].simulation.initial",
        )
        initialType = initialData.get("type")
        if initialType not in INITIAL_TYPES_3D:
            choices = ", ".join(sorted(INITIAL_TYPES_3D))
            raise ConfigError(f"layers[0].simulation.initial.type must be one of {choices}")
        if initialType == "catalog_default":
            initialType = catalogRule.recommendedInitial
        defaultDensity = catalogRule.density if initialType in {"sphere", "center_block"} else 0.2
        density = _asNumber(
            initialData.get("density", defaultDensity),
            "layers[0].simulation.initial.density",
            0,
            1,
        )
        radius = _asInteger(
            initialData.get("radius", max(1, gridSize // 4)),
            "layers[0].simulation.initial.radius",
            1,
            gridSize,
        )
        if initialType in {"sphere", "center_block"} and radius * 2 + 1 > gridSize:
            raise ConfigError("initial radius is too large for the configured 3D grid")
        origin = initialData.get("origin", "center")
        if origin not in {"center", "absolute"}:
            raise ConfigError("layers[0].simulation.initial.origin must be center or absolute")
        cells: tuple[tuple[int, int, int], ...] = ()
        if initialType == "cells":
            cellValues = initialData.get("cells", [])
            if not isinstance(cellValues, list):
                raise ConfigError("layers[0].simulation.initial.cells must be a list")
            parsedCells: list[tuple[int, int, int]] = []
            for index, cell in enumerate(cellValues):
                if not isinstance(cell, list) or len(cell) != 3:
                    raise ConfigError(f"layers[0].simulation.initial.cells[{index}] must contain [x, y, z]")
                coordinates = tuple(
                    _asInteger(value, f"layers[0].simulation.initial.cells[{index}][{axis}]", -80, 80)
                    for axis, value in enumerate(cell)
                )
                if boundary == "fixed":
                    offset = gridSize // 2 if origin == "center" else 0
                    if not all(0 <= value + offset < gridSize for value in coordinates):
                        raise ConfigError(f"layers[0].simulation.initial.cells[{index}] is outside the fixed grid")
                parsedCells.append(coordinates)
            cells = tuple(parsedCells)
        offsetCells = (0, 0, 0)
        if "offset_cells" in initialData:
            if initialType not in {"center_block", "sphere", "single", "cross"}:
                raise ConfigError("offset_cells is supported only for geometric 3D initializers")
            offsetValues = initialData["offset_cells"]
            if not isinstance(offsetValues, list) or len(offsetValues) != 3:
                raise ConfigError("layers[0].simulation.initial.offset_cells must contain [x, y, z]")
            offsetCells = tuple(
                _asInteger(value, f"layers[0].simulation.initial.offset_cells[{axis}]", -80, 80)
                for axis, value in enumerate(offsetValues)
            )
        initial = Initial3DConfig(initialType, density, radius, cells, origin, offsetCells=offsetCells)

    render = _asMapping(layerData.get("render"), "layers[0].render")
    _rejectUnknown(
        render,
        {
            "style",
            "palette",
            "voxel_scale",
            "surface_only",
            "color_by",
            "depth_shading",
            "vignette",
            "camera",
        },
        "layers[0].render",
    )
    renderStyle = render.get("style")
    if renderStyle not in {"isometric_voxel", "projected_voxel"}:
        raise ConfigError("layers[0].render.style must be isometric_voxel or projected_voxel")
    palette = render.get("palette", "wolfram3d" if simulationMode == "wolfram_3d_extruded" else rulePreset)
    if not isinstance(palette, str):
        raise ConfigError("layers[0].render.palette must be a string")
    try:
        getPalette3D(palette)
    except KeyError as error:
        raise ConfigError(str(error)) from error
    voxelScaleValue = render.get("voxel_scale", "auto")
    voxelScale = (
        0
        if voxelScaleValue == "auto"
        else _asInteger(voxelScaleValue, "layers[0].render.voxel_scale", 2, 64)
    )
    surfaceOnly = render.get("surface_only", True)
    if not isinstance(surfaceOnly, bool):
        raise ConfigError("layers[0].render.surface_only must be true or false")
    colorBy = render.get("color_by", "fixed")
    if colorBy not in PROJECTED_COLOR_MODES:
        choices = ", ".join(sorted(PROJECTED_COLOR_MODES))
        raise ConfigError(f"layers[0].render.color_by must be one of {choices}")
    depthShading = render.get("depth_shading", True)
    if not isinstance(depthShading, bool):
        raise ConfigError("layers[0].render.depth_shading must be true or false")
    vignette = render.get("vignette", False)
    if not isinstance(vignette, bool):
        raise ConfigError("layers[0].render.vignette must be true or false")
    camera = (
        _parseCamera(render["camera"], "layers[0].render.camera", projectCamera)
        if "camera" in render
        else None
    )
    if renderStyle == "isometric_voxel" and any(
        field in render for field in {"color_by", "depth_shading", "vignette", "camera"}
    ):
        raise ConfigError("projected render controls require the projected_voxel style")
    return Layer3DConfig(
        layerId,
        layerName.strip(),
        enabled,
        zIndex,
        opacity,
        stepIntervalMs,
        gridSize,
        boundary,
        parsedRule,
        rulePreset,
        initial,
        layerSeed,
        palette,
        voxelScale,
        surfaceOnly,
        renderStyle,
        colorBy,
        depthShading,
        vignette,
        camera,
        simulationMode,
        wolframRule,
        extrusionDepth,
        extrusionOffset,
    )


# :: ARRAY<STRING, ANY>, [ANY], layerConfig, INT, STRING, INT, outputConfig, (INT, INT, INT), path, cameraConfig -> projectConfig
# Parses remaining layers and completes a project model
def _completeProject(
    root: Mapping[str, Any],
    layers: list[Any],
    firstLayer: LayerConfig,
    schemaVersion: int,
    name: str,
    seed: int,
    output: OutputConfig,
    background: tuple[int, int, int],
    resolvedBaseDir: Path,
    camera: CameraConfig,
) -> ProjectConfig:
    parsedLayers = [firstLayer]
    for layerIndex, extraLayerData in enumerate(layers[1:], 1):
        extraProjectData = dict(root)
        extraProjectData["layers"] = [extraLayerData]
        try:
            parsedLayers.append(parseProject(extraProjectData, resolvedBaseDir).layer)
        except ConfigError as error:
            message = str(error).replace("layers[0]", f"layers[{layerIndex}]")
            raise ConfigError(message) from error
    layerIds = [parsedLayer.id for parsedLayer in parsedLayers]
    if len(layerIds) != len(set(layerIds)):
        raise ConfigError("layer IDs must be unique")
    return ProjectConfig(
        schemaVersion,
        name.strip(),
        seed,
        output,
        background,
        tuple(parsedLayers),
        resolvedBaseDir,
        camera,
    )


# :: ARRAY<STRING, ANY>, path? -> projectConfig
# Parses and validates a project mapping
def parseProject(data: Mapping[str, Any], baseDir: Path | None = None) -> ProjectConfig:
    resolvedBaseDir = baseDir or Path.cwd()
    root = _asMapping(data, "project")
    _rejectUnknown(root, {"schema_version", "project", "output", "canvas", "camera", "layers"}, "project")
    schemaVersion = _asInteger(root.get("schema_version"), "schema_version", 1, 1)

    projectData = _asMapping(root.get("project"), "project")
    _rejectUnknown(projectData, {"name", "seed"}, "project")
    name = projectData.get("name", "Untitled")
    if not isinstance(name, str) or not name.strip():
        raise ConfigError("project.name must be a non-empty string")
    seed = _asInteger(projectData.get("seed"), "project.seed", 0, 2**63 - 1)

    outputData = _asMapping(root.get("output"), "output")
    _rejectUnknown(
        outputData,
        {"path", "width", "height", "fps", "duration_seconds", "codec", "crf", "encoder_preset"},
        "output",
    )
    width = _asInteger(outputData.get("width"), "output.width", 320, 1920)
    height = _asInteger(outputData.get("height"), "output.height", 180, 1080)
    if width * 9 != height * 16:
        raise ConfigError("output width and height must have an exact 16:9 ratio")
    if width % 2 or height % 2:
        raise ConfigError("output width and height must both be even")
    fps = _asInteger(outputData.get("fps"), "output.fps", 1, 60)
    durationSeconds = _asNumber(outputData.get("duration_seconds"), "output.duration_seconds", 0.001, 60)
    outputPathValue = outputData.get("path", "out.mp4")
    if not isinstance(outputPathValue, str) or not outputPathValue.lower().endswith(".mp4"):
        raise ConfigError("output.path must be an .mp4 path")
    crf = _asInteger(outputData.get("crf", 18), "output.crf", 0, 51)
    if outputData.get("codec", "h264") != "h264":
        raise ConfigError("the current milestone supports only the h264 codec")
    encoderPreset = outputData.get("encoder_preset", "medium")
    if encoderPreset not in ENCODER_PRESETS:
        choices = ", ".join(sorted(ENCODER_PRESETS))
        raise ConfigError(f"output.encoder_preset must be one of {choices}")
    output = OutputConfig(Path(outputPathValue), width, height, fps, durationSeconds, crf, encoderPreset)
    if output.totalFrames < 1:
        raise ConfigError("output must contain at least one frame")

    canvas = _asMapping(root.get("canvas", {"background": "#0d1117"}), "canvas")
    _rejectUnknown(canvas, {"background"}, "canvas")
    background = _asColor(canvas.get("background", "#0d1117"), "canvas.background")
    camera = _parseCamera(root.get("camera", {}), "camera")

    layers = root.get("layers")
    if not isinstance(layers, list) or not 1 <= len(layers) <= 32:
        raise ConfigError("project.layers must contain between 1 and 32 layers")
    layerData = _asMapping(layers[0], "layers[0]")
    _rejectUnknown(
        layerData,
        {
            "id",
            "name",
            "seed",
            "enabled",
            "dimension",
            "z_index",
            "opacity",
            "step_interval_ms",
            "simulation",
            "render",
        },
        "layers[0]",
    )
    layerId = layerData.get("id")
    if not isinstance(layerId, str) or not LAYER_ID.fullmatch(layerId):
        raise ConfigError("layers[0].id must match ^[a-z][a-z0-9_-]{0,63}$")
    layerName = layerData.get("name", layerId)
    if not isinstance(layerName, str) or not layerName.strip():
        raise ConfigError("layers[0].name must be a non-empty string")
    layerSeed = (
        _asInteger(layerData.get("seed"), "layers[0].seed", 0, 2**63 - 1)
        if "seed" in layerData
        else None
    )
    enabled = layerData.get("enabled", True)
    if not isinstance(enabled, bool):
        raise ConfigError("layers[0].enabled must be true or false")
    dimension = layerData.get("dimension")
    if dimension not in {"2d", "3d"}:
        raise ConfigError("layers[0].dimension must be 2d or 3d")
    zIndex = _asInteger(layerData.get("z_index", 0), "layers[0].z_index", -10_000, 10_000)
    opacity = _asNumber(layerData.get("opacity", 1), "layers[0].opacity", 0, 1)
    stepIntervalMs = _asInteger(layerData.get("step_interval_ms", 100), "layers[0].step_interval_ms", 1, 60_000)

    if dimension == "3d":
        layer3D = _parseLayer3D(
            layerData,
            layerId,
            layerName,
            enabled,
            zIndex,
            opacity,
            stepIntervalMs,
            layerSeed,
            camera,
        )
        return _completeProject(
            root,
            layers,
            layer3D,
            schemaVersion,
            name,
            seed,
            output,
            background,
            resolvedBaseDir,
            camera,
        )

    simulation = _asMapping(layerData.get("simulation"), "layers[0].simulation")
    _rejectUnknown(simulation, {"mode", "grid", "rule", "initial"}, "layers[0].simulation")
    simulationMode = simulation.get("mode")
    if simulationMode not in {"outer_totalistic", "wolfram_2d"}:
        raise ConfigError("layers[0].simulation.mode must be outer_totalistic or wolfram_2d")
    ruleData = _asMapping(simulation.get("rule"), "layers[0].simulation.rule")
    wolframRule: int | None = None
    if simulationMode == "wolfram_2d":
        _rejectUnknown(ruleData, {"number"}, "layers[0].simulation.rule")
        wolframRule = _asInteger(ruleData.get("number"), "layers[0].simulation.rule.number", 0, 255)
        parsedRule: OuterTotalisticRule | None = None
        rulePreset: str | None = None
    else:
        _rejectUnknown(ruleData, {"preset", "notation", "neighborhood"}, "layers[0].simulation.rule")
        hasPreset = "preset" in ruleData
        hasNotation = "notation" in ruleData or "neighborhood" in ruleData
        if hasPreset == hasNotation:
            raise ConfigError("layers[0].simulation.rule must use either preset or notation with neighborhood")
        if hasPreset:
            preset = ruleData.get("preset")
            if not isinstance(preset, str):
                raise ConfigError("layers[0].simulation.rule.preset must be a string")
            try:
                catalogRule = getRule(preset)
                parsedRule = parseRule(catalogRule.notation, "moore")
            except (KeyError, ValueError) as error:
                raise ConfigError(str(error)) from error
            rulePreset = preset
        else:
            notation = ruleData.get("notation")
            neighborhood = ruleData.get("neighborhood")
            if not isinstance(notation, str) or not isinstance(neighborhood, str):
                raise ConfigError("custom rules require string notation and neighborhood")
            try:
                parsedRule = parseRule(notation, neighborhood)
            except ValueError as error:
                raise ConfigError(f"layers[0].simulation.rule: {error}") from error
            rulePreset = None

    grid = _asMapping(simulation.get("grid"), "layers[0].simulation.grid")
    _rejectUnknown(grid, {"size", "cell_size_px", "boundary"}, "layers[0].simulation.grid")
    boundary = grid.get("boundary", "wrap")
    if boundary not in {"wrap", "fixed"}:
        raise ConfigError("layers[0].simulation.grid.boundary must be wrap or fixed")
    if simulationMode == "wolfram_2d" and boundary != "wrap":
        raise ConfigError("Wolfram layers require a wrapped horizontal boundary")
    if "size" in grid and "cell_size_px" in grid:
        raise ConfigError("grid must use either size or cell_size_px, not both")
    cellSize: int | None = None
    if "size" in grid:
        sizeValue = grid["size"]
        if not isinstance(sizeValue, list) or len(sizeValue) != 2:
            raise ConfigError("layers[0].simulation.grid.size must contain [width, height]")
        gridWidth = _asInteger(sizeValue[0], "layers[0].simulation.grid.size[0]", 8, 2048)
        gridHeight = _asInteger(sizeValue[1], "layers[0].simulation.grid.size[1]", 8, 2048)
    else:
        cellSize = _asInteger(grid.get("cell_size_px", 4), "layers[0].simulation.grid.cell_size_px", 1, 128)
        gridWidth = math.ceil(width / cellSize)
        gridHeight = math.ceil(height / cellSize)

    initialData = _asMapping(simulation.get("initial"), "layers[0].simulation.initial")
    initialFields = (
        {"type", "density", "bits"}
        if simulationMode == "wolfram_2d"
        else {"type", "density", "radius", "size", "cells", "origin", "data", "path", "offset_px"}
    )
    _rejectUnknown(initialData, initialFields, "layers[0].simulation.initial")
    initialType = initialData.get("type")
    validInitialTypes = WOLFRAM_INITIAL_TYPES if simulationMode == "wolfram_2d" else INITIAL_TYPES
    if initialType not in validInitialTypes:
        choices = ", ".join(sorted(validInitialTypes))
        raise ConfigError(f"layers[0].simulation.initial.type must be one of {choices}")
    if initialType == "catalog_default":
        if rulePreset is None:
            raise ConfigError("catalog_default initialization requires a rule preset")
        initialType = getRule(rulePreset).recommendedInitial
    defaultDensity = 0.5 if simulationMode == "wolfram_2d" else 1
    density = _asNumber(
        initialData.get("density", defaultDensity),
        "layers[0].simulation.initial.density",
        0,
        1,
    )
    radius = _asInteger(initialData.get("radius", 2), "layers[0].simulation.initial.radius", 1, 2048)
    shapeSize: tuple[int, int] | None = None
    if "size" in initialData:
        shapeSizeValue = initialData["size"]
        if not isinstance(shapeSizeValue, list) or len(shapeSizeValue) != 2:
            raise ConfigError("layers[0].simulation.initial.size must contain [width, height]")
        shapeSize = (
            _asInteger(shapeSizeValue[0], "layers[0].simulation.initial.size[0]", 1, gridWidth),
            _asInteger(shapeSizeValue[1], "layers[0].simulation.initial.size[1]", 1, gridHeight),
        )
    if initialType in {"center_block", "disc"} and shapeSize is None:
        diameter = radius * 2 + 1
        if diameter > gridWidth or diameter > gridHeight:
            raise ConfigError("initial radius is too large for the configured grid")
    offsetPx = (0, 0)
    if "offset_px" in initialData:
        if initialType not in {"center_block", "disc"}:
            raise ConfigError("initial offset_px is supported only for center_block and disc")
        offsetValue = initialData["offset_px"]
        if not isinstance(offsetValue, list) or len(offsetValue) != 2:
            raise ConfigError("layers[0].simulation.initial.offset_px must contain [x, y]")
        offsetPx = (
            _asInteger(offsetValue[0], "layers[0].simulation.initial.offset_px[0]", -8192, 8192),
            _asInteger(offsetValue[1], "layers[0].simulation.initial.offset_px[1]", -8192, 8192),
        )
    origin = initialData.get("origin", "center")
    if origin not in {"center", "absolute"}:
        raise ConfigError("layers[0].simulation.initial.origin must be center or absolute")
    cells: tuple[tuple[int, int], ...] = ()
    if initialType == "cells":
        cellValues = initialData.get("cells", [])
        if not isinstance(cellValues, list):
            raise ConfigError("layers[0].simulation.initial.cells must be a list")
        parsedCells: list[tuple[int, int]] = []
        for index, cell in enumerate(cellValues):
            if not isinstance(cell, list) or len(cell) != 2:
                raise ConfigError(f"layers[0].simulation.initial.cells[{index}] must contain [x, y]")
            xValue = _asInteger(cell[0], f"layers[0].simulation.initial.cells[{index}][0]", -2048, 2048)
            yValue = _asInteger(cell[1], f"layers[0].simulation.initial.cells[{index}][1]", -2048, 2048)
            if boundary == "fixed":
                offsetX = gridWidth // 2 if origin == "center" else 0
                offsetY = gridHeight // 2 if origin == "center" else 0
                if not (0 <= xValue + offsetX < gridWidth and 0 <= yValue + offsetY < gridHeight):
                    raise ConfigError(f"layers[0].simulation.initial.cells[{index}] is outside the fixed grid")
            parsedCells.append((xValue, yValue))
        cells = tuple(parsedCells)
    rleData = initialData.get("data")
    rlePathValue = initialData.get("path")
    rlePath: Path | None = None
    if initialType == "rle":
        if (rleData is None) == (rlePathValue is None):
            raise ConfigError("RLE initialization requires exactly one of data or path")
        if rleData is not None:
            if not isinstance(rleData, str):
                raise ConfigError("layers[0].simulation.initial.data must be a string")
            try:
                pattern = parseRle(rleData)
            except ValueError as error:
                raise ConfigError(f"layers[0].simulation.initial.data: {error}") from error
            if boundary == "fixed" and (pattern.shape[1] > gridWidth or pattern.shape[0] > gridHeight):
                raise ConfigError("RLE pattern is larger than the fixed grid")
        if rlePathValue is not None:
            if not isinstance(rlePathValue, str) or not rlePathValue.strip():
                raise ConfigError("layers[0].simulation.initial.path must be a non-empty string")
            rlePath = Path(rlePathValue)
            source = rlePath if rlePath.is_absolute() else resolvedBaseDir / rlePath
            try:
                pattern = parseRle(source.read_text(encoding="utf-8"))
            except OSError as error:
                raise ConfigError(f"could not read RLE file {source}: {error}") from error
            except ValueError as error:
                raise ConfigError(f"layers[0].simulation.initial.path: {error}") from error
            if boundary == "fixed" and (pattern.shape[1] > gridWidth or pattern.shape[0] > gridHeight):
                raise ConfigError("RLE pattern is larger than the fixed grid")

    bits: tuple[int, ...] = ()
    if initialType == "bits":
        bitValues = initialData.get("bits")
        if not isinstance(bitValues, list) or not bitValues:
            raise ConfigError("layers[0].simulation.initial.bits must be a non-empty list")
        if len(bitValues) > gridWidth:
            raise ConfigError("layers[0].simulation.initial.bits is wider than the grid")
        bits = tuple(
            _asInteger(bit, f"layers[0].simulation.initial.bits[{index}]", 0, 1)
            for index, bit in enumerate(bitValues)
        )

    initial = Initial2DConfig(
        initialType,
        density,
        radius,
        shapeSize,
        cells,
        origin,
        rleData,
        rlePath,
        bits,
        offsetPx,
    )

    render = _asMapping(layerData.get("render"), "layers[0].render")
    _rejectUnknown(render, {"style", "color", "layout"}, "layers[0].render")
    if render.get("style", "cells") != "cells":
        raise ConfigError("the current milestone supports only the cells render style")
    liveColor = _asColor(render.get("color", "#e8f4ff"), "layers[0].render.color")
    layout = render.get("layout", "fit")
    if layout not in {"fit", "cover"}:
        raise ConfigError("layers[0].render.layout must be fit or cover")

    layer = Layer2DConfig(
        layerId,
        layerName.strip(),
        enabled,
        zIndex,
        opacity,
        stepIntervalMs,
        gridWidth,
        gridHeight,
        boundary,
        density,
        liveColor,
        layout,
        parsedRule,
        rulePreset,
        initial,
        layerSeed,
        cellSize,
        simulationMode,
        wolframRule,
    )
    return _completeProject(
        root,
        layers,
        layer,
        schemaVersion,
        name,
        seed,
        output,
        background,
        resolvedBaseDir,
        camera,
    )


# :: STRING|path -> projectConfig
# Loads and validates a project from disk
def loadProject(path: str | Path) -> ProjectConfig:
    projectPath = Path(path).expanduser().resolve()
    try:
        with projectPath.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        raise ConfigError(f"could not read project {projectPath}: {error}") from error
    return parseProject(data, projectPath.parent)


# :: projectConfig, STRING|path -> projectConfig
# Atomically writes a normalized project and returns its rebased model
def saveProject(project: ProjectConfig, path: str | Path) -> ProjectConfig:
    projectPath = Path(path).expanduser().resolve()
    projectPath.parent.mkdir(parents=True, exist_ok=True)
    rebased = parseProject(project.toDict(), projectPath.parent)
    temporaryPath: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=projectPath.parent,
            prefix=f".{projectPath.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporaryPath = Path(handle.name)
            json.dump(rebased.toDict(), handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporaryPath, projectPath)
    except OSError as error:
        if temporaryPath is not None:
            temporaryPath.unlink(missing_ok=True)
        raise ConfigError(f"could not save project {projectPath}: {error}") from error
    return rebased


# :: path? -> projectConfig
# Creates the default editable two-dimensional project
def defaultProject(baseDir: Path | None = None) -> ProjectConfig:
    return parseProject(
        {
            "schema_version": 1,
            "project": {"name": "Untitled Life", "seed": 7},
            "output": {
                "path": "life.mp4",
                "width": 640,
                "height": 360,
                "fps": 30,
                "duration_seconds": 5,
                "crf": 18,
                "encoder_preset": "medium",
            },
            "canvas": {"background": "#0d1117"},
            "layers": [
                {
                    "id": "life",
                    "name": "Conway's Life",
                    "enabled": True,
                    "dimension": "2d",
                    "z_index": 0,
                    "opacity": 1,
                    "step_interval_ms": 100,
                    "simulation": {
                        "mode": "outer_totalistic",
                        "grid": {"size": [160, 90], "boundary": "wrap"},
                        "rule": {"preset": "life"},
                        "initial": {"type": "random", "density": 0.3},
                    },
                    "render": {"style": "cells", "color": "#e8f4ff", "layout": "fit"},
                }
            ],
        },
        baseDir,
    )
