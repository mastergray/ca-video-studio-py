# CA Video Generator

CA Video Generator is a native Python/PySide6 desktop application for designing,
previewing, saving, and rendering deterministic cellular-automata videos. It can
combine independently timed 2D and 3D automata in one scene and export H.264 MP4
video at up to 1920×1080 and 60 seconds.

The normal workflow is entirely graphical. Launch the application without a
project argument, build the scene in the editor, save it through the native file
dialog, and render the video from the Render menu. JSON is the project storage
format, but it does not need to be written or passed through the command line.

## Features

- Layered 2D outer-totalistic automata with catalog or custom B/S/C rules.
- Elementary Wolfram rules 0–255 rendered as scrolling histories.
- Catalog-driven outer-totalistic 3D automata.
- Extruded Wolfram 3D histories.
- Isometric and rotating camera-projected 3D rendering.
- Global project seed with optional deterministic per-layer overrides.
- Random, geometric, explicit-cell, RLE, and Wolfram initial conditions.
- Solid or editable state-gradient 2D coloring.
- Per-layer opacity, fades, and independently colored 2D trails.
- Native project New, Open, Save, and Save As actions.
- Deterministic preview and H.264 MP4 export through the same rendering pipeline.

The [roadmap](ROADMAP.md) describes planned work, while the full contracts live
in the [product specification](docs/ca-video-spec.md) and
[native UI design](docs/native-ui-design.md).

## Install and launch

Requirements:

- Python 3.10 or newer.
- [uv](https://docs.astral.sh/uv/) for the documented local workflow.
- FFmpeg built with the `libx264` encoder.
- `libxcb-cursor0` when running through X11 on Ubuntu.

Install the environment and open a new untitled project:

```bash
uv sync
uv run ca-video
```

No project file is required at launch.

## UI quick start

### 1. Create or open a project

Launching the application creates a usable default 2D project. Use the toolbar
or File menu to manage projects:

- **New Project** starts from the default scene.
- **Open Project…** opens an existing `.cav.json` project through a native file
  dialog.
- **Save** updates the current project file. The first save opens the Save As
  dialog.
- **Save As…** writes a new project file.

The title bar displays `*` when the project has unsaved changes. New, Open, and
Quit ask whether to save when unsaved changes are present. Saves use a temporary
sibling file and atomic replacement so a failed write does not partially replace
the previous project.

### 2. Build the layer stack

Use **+ Add Layer** in the left pane to add one of four layer families:

- **2D Automaton**
- **Wolfram 2D History**
- **3D Automaton**
- **Wolfram 3D Extrusion**

The top row is composited last and therefore appears in front. Select a layer to
edit it, use the arrow buttons to change its order, or use Duplicate and Delete
to manage the stack. The checkbox beside a layer enables or disables it.

### 3. Configure the selected layer

The **Layer** inspector tab is contextual and hides settings that do not apply
to the selected layer.

- **General** controls the layer name and whether its seed is derived from the
  project seed or explicitly overridden.
- **Simulation** selects the rule family, rule, logical grid, boundary behavior,
  and related options.
- **Initial Condition** selects how the first generation is populated. Available
  controls depend on the layer family and initializer.
- **Appearance** controls opacity, fade rate, 2D color mode and trails, or 3D
  renderer, palette, coloring, and voxel settings.
- **Camera** appears for camera-projected 3D layers.
- **Timing** controls the interval between automaton generations.

Simulation changes reset the preview to frame zero. Visual changes such as
color, opacity, fade, and trail settings update the current frame without
resetting the automaton when possible.

### 4. Configure the project and output

The **Project** inspector tab contains the project-wide controls:

- Project name and global random seed.
- Export resolution, frame rate, and duration.
- Canvas background color.

Output presets use a 16:9 aspect ratio and range up to 1920×1080. Duration is
limited to 60 seconds.

### 5. Preview the animation

Use the controls below the preview:

- **Play/Pause** runs the presentation clock.
- **Step** advances exactly one automaton generation.
- **Reset** returns every layer to its deterministic initial state.

The HUD reports presentation time, selected-layer generation, live-cell count,
grid dimensions, and rule. Preview rendering is capped at 640×360 and 30 fps so
choosing a larger export size or frame rate does not slow the editor. Export uses
the selected full resolution and frame rate.

### 6. Render an MP4

Choose **Render → Render Video…** or use the Render Video toolbar action. Select
an `.mp4` destination in the native file dialog. Rendering runs in a background
worker with frame progress and cancellation controls, leaving the application
responsive.

The export uses the same simulation clock, layer composition, colors, fades,
trails, and camera calculations as the preview. A saved project therefore
reproduces the same video when rendered again with the same application version
and seed.

## Core concepts

### Seeds and determinism

The project seed is the default source of randomness for every layer. A layer
with **Derived from project** receives a stable seed based on the project seed
and layer ID. Choose **Custom** to make that layer independent of later project
seed changes.

Resetting or reopening a saved project reconstructs the same initial grids and
generation sequence.

### Grid size, cell size, and output resolution

The simulation grid is independent of the video raster:

- **Fixed grid size** sets the logical width and height in cells.
- **Cell size from export** derives the logical grid from the export resolution
  and desired cell size in pixels.
- **Fit** shows the full grid and letterboxes when its aspect ratio differs from
  the canvas.
- **Cover** fills the canvas and center-crops excess grid raster.

Changing export resolution does not make the live preview render at that larger
size. It can, however, change the logical grid when the layer uses export-relative
cell size.

### State gradients, fades, and trails

For a 2D layer, **Solid** uses one live-cell color. **State gradient** exposes
two through eight native color stops and maps them across the nonzero states of
a Generations rule, from the live state through the last decay state. A binary
rule has only one nonzero state and therefore uses the first stop.

Fade rate controls how quickly cells visually enter or leave without changing
simulation state. A fading cell retains its last state color. Trail amount stores
time-based historical presence beneath cells and always uses its separate trail
color.

## Example projects

Use **File → Open Project…** and choose one of these files:

| Example | Demonstrates |
| --- | --- |
| [`examples/life.cav.json`](examples/life.cav.json) | Conway's Life and the basic 2D workflow |
| [`examples/layered-life.cav.json`](examples/layered-life.cav.json) | Multiple independently timed 2D layers |
| [`examples/state-gradient.cav.json`](examples/state-gradient.cav.json) | Generations colors, fading, and trails |
| [`examples/wolfram-rule-30.cav.json`](examples/wolfram-rule-30.cav.json) | Scrolling Wolfram Rule 30 history |
| [`examples/isometric-445.cav.json`](examples/isometric-445.cav.json) | Isometric outer-totalistic 3D voxels |
| [`examples/projected-crystal.cav.json`](examples/projected-crystal.cav.json) | Rotating camera-projected crystal voxels |
| [`examples/wolfram-3d-rule-30.cav.json`](examples/wolfram-3d-rule-30.cav.json) | Extruded Wolfram Rule 30 volume |

## Keyboard shortcuts

| Action | Shortcut |
| --- | --- |
| New project | `Ctrl+N` |
| Open project | `Ctrl+O` |
| Save | `Ctrl+S` |
| Save As | `Ctrl+Shift+S` |
| Play or pause | `Space` |
| Reset preview | `Ctrl+R` |
| Preview-only mode | `Tab` |
| Full screen | `F11` |
| Render video | `Ctrl+Shift+R` |

## Project files and optional CLI tools

Projects are stored as validated UTF-8 JSON with the recommended `.cav.json`
suffix. The editor owns this format during normal use; manual JSON editing is
not required.

For automation, continuous integration, or troubleshooting, saved projects may
optionally be validated or rendered without opening the UI:

```bash
uv run ca-video validate examples/life.cav.json
uv run ca-video render examples/life.cav.json --output renders/life.mp4
```

Passing a project directly when launching the GUI is also supported as a
convenience for file associations and development:

```bash
uv run ca-video gui examples/life.cav.json
```

These commands are optional and are not part of the normal editor workflow.

## Development

Run static checks and the complete test suite:

```bash
uv run ruff check src tests
uv run pytest
```

Development and repository conventions are documented in
[`CONTRIBUTING.md`](CONTRIBUTING.md).
