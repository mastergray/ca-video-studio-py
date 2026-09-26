from __future__ import annotations  # Enable forward references in type annotations

import json  # Parse persisted project files
import math  # Validate finite numeric settings and derive grid dimensions
import re  # Validate color and identifier formats
from collections.abc import Mapping  # Describe unvalidated JSON objects
from decimal import Decimal, InvalidOperation  # Calculate exact output frame counts
from pathlib import Path  # Represent project and output paths
from typing import Any  # Describe values before schema validation

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


# Stores validated settings for the milestone's single 2D layer
class Layer2DConfig:

    # CONSTRUCTOR :: STRING, STRING, BOOL, INT, FLOAT, INT, INT, INT, STRING, FLOAT, (INT, INT, INT), STRING -> layer2DConfig
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

    #
    # Properties
    #

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


# Stores a fully validated project configuration
class ProjectConfig:

    # CONSTRUCTOR :: INT, STRING, INT, outputConfig, (INT, INT, INT), layer2DConfig, path -> projectConfig
    # Creates immutable-by-convention project settings
    def __init__(
        self,
        schemaVersion: int,
        name: str,
        seed: int,
        output: OutputConfig,
        canvasBackground: tuple[int, int, int],
        layer: Layer2DConfig,
        baseDir: Path,
    ) -> None:
        self._schemaVersion = schemaVersion
        self._name = name
        self._seed = seed
        self._output = output
        self._canvasBackground = canvasBackground
        self._layer = layer
        self._baseDir = baseDir

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

    # PROPERTY :: VOID -> layer2DConfig
    # Returns the configured layer
    @property
    def layer(self) -> Layer2DConfig:
        return self._layer

    # PROPERTY :: VOID -> path
    # Returns the project-relative base directory
    @property
    def baseDir(self) -> Path:
        return self._baseDir

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
            self._layer,
            self._baseDir,
        )


# :: ARRAY<STRING, ANY>, path? -> projectConfig
# Parses and validates a project mapping
def parseProject(data: Mapping[str, Any], baseDir: Path | None = None) -> ProjectConfig:
    root = _asMapping(data, "project")
    _rejectUnknown(root, {"schema_version", "project", "output", "canvas", "layers"}, "project")
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

    layers = root.get("layers")
    if not isinstance(layers, list) or len(layers) != 1:
        raise ConfigError("the current milestone requires exactly one layer")
    layerData = _asMapping(layers[0], "layers[0]")
    _rejectUnknown(
        layerData,
        {"id", "name", "enabled", "dimension", "z_index", "opacity", "step_interval_ms", "simulation", "render"},
        "layers[0]",
    )
    layerId = layerData.get("id")
    if not isinstance(layerId, str) or not LAYER_ID.fullmatch(layerId):
        raise ConfigError("layers[0].id must match ^[a-z][a-z0-9_-]{0,63}$")
    layerName = layerData.get("name", layerId)
    if not isinstance(layerName, str) or not layerName.strip():
        raise ConfigError("layers[0].name must be a non-empty string")
    enabled = layerData.get("enabled", True)
    if not isinstance(enabled, bool):
        raise ConfigError("layers[0].enabled must be true or false")
    if layerData.get("dimension") != "2d":
        raise ConfigError("the current milestone supports only a 2d layer")
    zIndex = _asInteger(layerData.get("z_index", 0), "layers[0].z_index", -10_000, 10_000)
    opacity = _asNumber(layerData.get("opacity", 1), "layers[0].opacity", 0, 1)
    stepIntervalMs = _asInteger(
        layerData.get("step_interval_ms", 100),
        "layers[0].step_interval_ms",
        1,
        60_000,
    )

    simulation = _asMapping(layerData.get("simulation"), "layers[0].simulation")
    _rejectUnknown(simulation, {"mode", "grid", "rule", "initial"}, "layers[0].simulation")
    if simulation.get("mode") != "outer_totalistic":
        raise ConfigError("the current milestone supports only outer_totalistic simulation")
    rule = _asMapping(simulation.get("rule"), "layers[0].simulation.rule")
    _rejectUnknown(rule, {"preset"}, "layers[0].simulation.rule")
    if rule.get("preset") != "life":
        raise ConfigError("the current milestone supports only the life rule preset")
    grid = _asMapping(simulation.get("grid"), "layers[0].simulation.grid")
    _rejectUnknown(grid, {"size", "cell_size_px", "boundary"}, "layers[0].simulation.grid")
    boundary = grid.get("boundary", "wrap")
    if boundary not in {"wrap", "fixed"}:
        raise ConfigError("layers[0].simulation.grid.boundary must be wrap or fixed")
    if "size" in grid and "cell_size_px" in grid:
        raise ConfigError("grid must use either size or cell_size_px, not both")
    if "size" in grid:
        size = grid["size"]
        if not isinstance(size, list) or len(size) != 2:
            raise ConfigError("layers[0].simulation.grid.size must contain [width, height]")
        gridWidth = _asInteger(size[0], "layers[0].simulation.grid.size[0]", 8, 2048)
        gridHeight = _asInteger(size[1], "layers[0].simulation.grid.size[1]", 8, 2048)
    else:
        cellSize = _asInteger(
            grid.get("cell_size_px", 4),
            "layers[0].simulation.grid.cell_size_px",
            1,
            128,
        )
        gridWidth = math.ceil(width / cellSize)
        gridHeight = math.ceil(height / cellSize)

    initial = _asMapping(simulation.get("initial"), "layers[0].simulation.initial")
    _rejectUnknown(initial, {"type", "density"}, "layers[0].simulation.initial")
    if initial.get("type") != "random":
        raise ConfigError("the current milestone supports only random initialization")
    density = _asNumber(initial.get("density", 0.3), "layers[0].simulation.initial.density", 0, 1)

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
        layerName,
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
    )
    return ProjectConfig(
        schemaVersion,
        name.strip(),
        seed,
        output,
        background,
        layer,
        baseDir or Path.cwd(),
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


# :: path? -> projectConfig
# Creates the default milestone project
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
