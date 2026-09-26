# CA Video Generator — Product and Technical Specification

Status: Draft for implementation
Version: 0.3
Date: 2026-09-26

## 1. Summary

CA Video Generator is a local-first Python application for designing, previewing, and exporting deterministic cellular-automata videos. It combines the offline MP4 workflow in `ref/ca_video` with the useful visual and simulation options in `midi-ca-server-2`: layered 2D and 3D automata, larger rule and palette catalogs, independent layer timing, Wolfram modes, smooth visual transitions, and isometric voxel rendering.

The application must export H.264 MP4 video at a 16:9 aspect ratio, up to 1920×1080, up to 60 seconds long. A saved project must render identically when run again with the same application version, project file, and random seed.

This product is an offline video generator, not a live performance server. MIDI, HTTP/SSE events, note-driven seeding, event filters, channel collisions, dynamic rule or palette switching, destroy/control events, and event-triggered mutations are outside the initial scope.

## 2. Product decisions

The first implementation will use these decisions unless this specification is revised:

- The application is a native, local-only Python desktop application.
- The primary UX is a PySide6/Qt Widgets editor. It does not start a web server, open a browser, or listen on a network port.
- A CLI exposes validation and rendering for repeatable and headless use.
- JSON is the canonical project format. The application publishes a JSON Schema for it.
- Simulation is resolution-independent except when a 2D layer explicitly uses `cell_size_px` to derive its grid from the export canvas.
- Export is deterministic and frame-driven; real wall-clock timing never affects a render.
- Each layer owns one automaton. Layers composite visually but do not exchange cells.
- Output contains video only. Audio generation, audio analysis, and soundtrack muxing are not part of version 1.
- Direct execution of JavaScript scene files from `midi-ca-server-2` is not supported.

### 2.1 Verified desktop runtime

The initial supported development target is:

- Ubuntu 20.04 x86-64 with X11.
- Python 3.11.
- PySide6 6.9.3, pinned because its x86-64 wheel supports glibc 2.28 and later.
- The `libxcb-cursor0` system package for Qt's X11 platform plugin.
- FFmpeg with `libx264` support.

On 2026-09-26, the target machine successfully opened a native Qt Widgets window through the `xcb` platform plugin, created a 1920×1080 RGB `QImage`, and initialized a valid `QOpenGLWidget` with an OpenGL 4.6 context. These smoke tests must be preserved as automated or documented environment checks.

Qt Widgets is the version 1 UI technology. NumPy-rendered preview frames are presented through `QImage` by default. `QOpenGLWidget` may be used for display acceleration after profiling, but the simulation and authoritative offline renderer must not require OpenGL.

## 3. Goals

### 3.1 User goals

A user can:

1. Create a new project from a useful preset.
2. Configure exact output resolution, frame rate, and duration.
3. Add, remove, duplicate, enable, disable, and reorder 2D or 3D layers.
4. Select a built-in cellular-automaton rule or enter a custom outer-totalistic rule.
5. Select an initial condition and obtain repeatable output from a seed.
6. Configure colors, palettes, opacity, trails, fades, 3D projection, and camera motion.
7. Preview, pause, single-step, reset, and scrub by restarting at a selected time.
8. Save and reopen the complete project.
9. Validate a project before committing to a render.
10. Render an MP4 with progress, elapsed time, estimated time remaining, and cancellation.
11. Render the same project from the command line.

### 3.2 Engineering goals

- Separate configuration, simulation, rendering, compositing, and encoding.
- Keep simulation code independent of the editor and encoder.
- Stream frames to the encoder; do not retain an entire video in memory.
- Make built-in rule and palette catalogs data-driven.
- Make failures actionable: validation errors identify the JSON path and valid range or alternatives.
- Preserve project compatibility through an explicit `schema_version` and migrations.

## 4. Non-goals for version 1

- Live MIDI input or MIDI-file playback.
- HTTP event ingestion, SSE, or forwarding to another service.
- An event timeline or keyframe editor.
- Note-driven seeding, rule switching, palette switching, destruction, or transport control.
- Probabilistic or event-driven rule mutation during a render.
- Multiple competing channels/species within one grid or collision rules between them.
- Scene switching inside one exported video.
- Audio synthesis, audio-reactive behavior, or audio muxing.
- Cloud rendering, user accounts, collaboration, or remote access.
- Arbitrary Python or JavaScript execution from a project file.
- Guaranteed real-time preview or real-time 1080p export.

## 5. Source baseline and intended parity

### 5.1 Existing Python proof of concept

The proof of concept already demonstrates:

- JSON-configured 2D and 3D outer-totalistic automata.
- Life-like and Generations rules in `B…/S…/C…` notation.
- Moore and von Neumann neighborhoods.
- Wrapped and fixed boundaries.
- Random, centered, spherical, explicit-cell, and 2D RLE initialization.
- 2D gradients and trails.
- Projected 3D voxels with camera rotation, depth shading, and state/height/distance coloring.
- H.264 MP4 encoding through ImageIO/FFmpeg.

Known proof-of-concept behavior is not automatically contractual. In particular, output dimensions must not be silently rounded to multiples of 16, and duration must be defined directly rather than inferred from simulation steps plus hold frames.

### 5.2 Options adopted from `midi-ca-server-2`

The application will adopt:

- Multiple independently timed visual layers.
- Background/foreground ordering generalized as numeric `z_index`.
- 2D and 3D rule catalogs.
- Elementary Wolfram rules 0–255 in a scrolling 2D presentation.
- The reference server's extruded 3D Wolfram presentation.
- Per-layer step interval, opacity, fade rate, and display scale.
- Isometric 3D voxels and face palettes.
- 3D grid-size and fixed/automatic voxel sizing controls.
- Play, pause, step, reset, and useful preview statistics.
- Scene/project editing and reusable presets.

The application will not port the server's channels, collisions, event filters, live routes, SSE loader, or controller integration in version 1.

## 6. Output contract

### 6.1 Video limits

- Container: MP4.
- Default codec: H.264 (`libx264`).
- Pixel format: `yuv420p` for broad playback compatibility.
- Aspect ratio: exactly 16:9, checked with `width * 9 == height * 16`.
- Maximum dimensions: 1920×1080.
- Minimum dimensions: 320×180.
- Width and height must both be even.
- Duration: greater than 0 and no more than 60 seconds.
- Frame rate: integer from 1 through 60; editor presets are 24, 25, 30, 50, and 60 fps.
- No dimension is silently rounded, cropped, or increased by validation or encoding.

Editor resolution presets:

- 640×360
- 960×540
- 1280×720
- 1920×1080

Custom dimensions are accepted when they satisfy all constraints.

### 6.2 Frame count and duration

`total_frames = round(duration_seconds * fps)`.

The project is invalid when `duration_seconds * fps` is not within `1e-6` of an integer. This avoids ambiguous duration rounding. Frame zero represents simulation time `t = 0`; subsequent frames represent `frame_index / fps`. The encoder receives exactly `total_frames` frames.

Optional start and end holds are expressed in seconds and are included in, not added to, `duration_seconds`. Their converted frame counts must be integral, and their sum must be less than or equal to the total frame count.

### 6.3 Encoding options

The editor exposes:

- Quality preset: Draft, Standard, High, or Custom.
- H.264 CRF for Custom, valid range 0–51; default 18.
- Encoder speed preset; default `medium`.
- Output path, which must end in `.mp4`.
- Overwrite confirmation when the destination already exists.

Rendering writes to a sibling temporary file and renames it to the final path only after the encoder closes successfully. Cancellation or failure must not replace an existing completed output.

## 7. Deterministic clock and simulation semantics

### 7.1 Render clock

Each layer has an independent `step_interval_ms`. At each output frame:

1. Compute the frame's exact rational presentation time from its index and fps.
2. Advance each active layer through every simulation step due at or before that presentation time.
3. Update visual interpolation for one frame interval.
4. Render each layer.
5. Composite layers in stable order.
6. Send the resulting RGB frame to the encoder.

The initial frame is rendered before any simulation step unless `simulation.initial_step` is `true`. A layer may take zero, one, or multiple simulation steps between output frames. Floating-point accumulation must not determine whether a step occurs; use integer or rational time units.

During a start hold, simulation and camera motion are frozen. During an end hold, simulation is frozen; camera motion continues only when `holds.rotate_camera_at_end` is `true`.

### 7.2 Randomness

- Every project has a required integer master seed in the range 0 through `2^63 - 1`.
- Each layer derives an independent random stream from the master seed and stable layer ID.
- A layer may set an optional integer `seed` override in the same range. When
  present, that exact seed replaces derivation from the project seed.
- The editor exposes Derived and Custom seed modes and displays the resolved
  seed used by the selected layer.
- Random stream derivation must not use Python's process-randomized `hash()`.
- Initialization and any render sampling consume documented streams in a stable order.
- Preview Reset returns the layer to the same initial state.
- Changing layer order must not change another layer's random initialization.

The exact pseudorandom generator and stream-derivation method are recorded in render metadata and treated as compatibility-sensitive.

### 7.3 Cell state model

Outer-totalistic layers use an unsigned integer cell state:

- `0`: dead and eligible for birth.
- `1`: alive and counted as a neighbor.
- `2..states-1`: decay states; not counted as alive and not eligible for birth.

For each generation:

- A dead cell is born when its live-neighbor count is in the birth set.
- A live cell survives when its count is in the survival set.
- In a two-state rule, a non-surviving live cell becomes dead.
- In a rule with three or more states, a non-surviving live cell enters state 2; decay states increment and return to 0 after the final state.

### 7.4 Neighborhoods and boundaries

Supported neighborhoods:

- 2D Moore: 8 neighbors.
- 2D von Neumann: 4 neighbors.
- 3D Moore: 26 neighbors.
- 3D von Neumann: 6 neighbors.

Supported boundaries:

- `wrap`: toroidal indexing on every axis.
- `fixed`: cells beyond the grid are dead.

### 7.5 Outer-totalistic rule format

Rules may use a preset name or custom notation:

- `B3/S23`
- `B2/S/C3`
- `B4/S4-5/C5`
- `B13-14,17-19/S13-26/C2`

`B` is the birth set, `S` is the survival set, and optional `C` or `G` is the number of states. Commas and inclusive ranges are required for ambiguous multi-digit counts. Counts outside the chosen neighborhood's possible range are validation errors rather than silently ignored.

### 7.6 Wolfram modes

All elementary Wolfram rules from 0 through 255 are supported.

- `wolfram_2d`: a 1D row evolves and scrolls through a 2D grid. Each generation removes the oldest row and appends the newest row.
- `wolfram_3d_extruded`: the same evolving row is extruded through a configurable depth band and scrolled through the 3D grid, matching the visual idea in the reference server.
- The Wolfram horizontal boundary wraps.
- Initial row modes are `single_center`, `random`, and explicit `bits`.
- A new 2D Wolfram grid is prefilled from top to bottom with successive
  generations, matching the reference server, so frame zero contains a useful
  rule history. Subsequent simulation steps scroll that history upward.
- Explicit `bits` are a non-empty array of zeroes and ones no wider than the
  grid. Short patterns are centered in the starting row.
- A 2D Wolfram simulation is encoded as `mode: "wolfram_2d"`, a rule object
  containing `number` from 0 through 255, and one of these initial objects:
  `{ "type": "single_center" }`, `{ "type": "random", "density": 0.5 }`, or
  `{ "type": "bits", "bits": [1, 0, 1] }`.
- Wolfram layers do not accept outer-totalistic `birth`, `survival`, `states`, `neighborhood`, or general-purpose initial-condition fields.

## 8. Built-in catalogs

Catalog entries contain a stable key, display name, dimension, rule definition, description, recommended initialization, and optional recommended palette. Catalogs live in versioned data files rather than UI code.

### 8.1 Required 2D rule keys

Port these reference keys:

`life`, `highlife`, `longlife`, `life34`, `seeds`, `brian`, `starwars`, `replicator`, `morley`, `two_by_two`, `daynight`, `diamoeba`, `anneal`, `coag`, `stains`, `maze`, `mazectric`, `walled`, `vote`, `vote45`.

### 8.2 Required 3D rule keys

Port these reference keys:

`445`, `amoeba`, `builder`, `architecture`, `fortress`, `platter`, `cubic`, `pyroclastic`, `pulse`, `blinker3d`, `slow_blob`, `electrified`, `coral`, `crystal`, `diamoeba3d`, `spiky`, `shell`, `symmetrica`, `snowflake`, `growth`, `creep`, `coral_wall`, `sticks`, `pyro`, `cloud`, `bugs3d`, `fireworks`, `chaos3d`, `nova`, `static3d`, `slow_decay`, `maze3d`.

### 8.3 Required palettes

- Port the four-face 3D palettes from `P3D`, including `wolfram3d`.
- Preserve palette keys even when they share a name with a rule.
- Support custom face colors: top, left, right, and outline.
- Support a custom state gradient for Generations rules.
- Support a solid RGB color for ordinary 2D live cells.
- Support note-derived palettes only if they are exposed as a static hue choice; no note or event input is required.

## 9. Initial conditions

Outer-totalistic layers support:

- `random`: fill the full grid using `density` from 0 through 1.
- `center_block`: centered rectangle/cuboid using `radius` or explicit size and density.
- `disc` / `sphere`: centered radius and density; disc is 2D, sphere is 3D.
- `cells`: explicit `[x, y]` or `[x, y, z]` coordinates with `origin` of `absolute` or `center`.
- `rle`: inline RLE text or an RLE file path, 2D only.
- `catalog_default`: use the selected preset rule's recommended `single`, `cross`, or `blob` initializer.

Initialization requirements:

- An empty explicit cell list is allowed but produces a warning.
- Out-of-bounds explicit cells are errors under fixed boundaries and normalized under wrapped boundaries.
- RLE headers and comments are accepted. Unsupported multistate RLE symbols produce a clear error.
- A pattern larger than a fixed grid is an error. Under wrapped boundaries it is allowed and wraps deterministically.
- Density is applied only within the selected initialization shape.
- Two-dimensional `center_block` and `disc` initializers accept optional
  `offset_px: [x, y]` values from -8192 through 8192. Positive X moves right;
  positive Y moves down. `(0, 0)` is the export-canvas center.
- Pixel offsets are converted to the nearest logical cell using the exact
  export `fit` or `cover` raster scale, with half-cell ties rounded away from
  zero. Preview uses that same resolved grid position rather than converting
  against its smaller raster.
- Offset geometric shapes clip at fixed grid edges and wrap deterministically
  at wrapped edges. A zero offset is omitted from normalized project JSON.

## 10. Layers and composition

### 10.1 Common layer fields

Each layer has:

- Stable unique `id`.
- User-facing `name`.
- `enabled`.
- `dimension`: `2d` or `3d`.
- `z_index`; lower values render first.
- Stable list position as the tie-breaker for equal `z_index`.
- `opacity` from 0 through 1.
- `step_interval_ms`, minimum 1.
- Optional `seed` override; when omitted, the seed is derived from the project
  master seed and stable layer ID.
- `simulation` configuration.
- `render` configuration.

Version 1 uses normal source-over alpha compositing. Additional blend modes may be added in a later schema version.

### 10.2 Layer independence

Layers have separate grids, clocks, rules, and random streams. They do not share neighbor counts, collide, seed each other, or mutate each other's rules. A 2D background can therefore evolve at a different rate from a 3D foreground without coupling their simulation state.

### 10.3 2D grid sizing

A 2D layer chooses exactly one sizing mode:

- Explicit `size: [width, height]`, each axis from 8 through 2048 cells.
- `cell_size_px`, from 1 through 128, which derives the grid as `ceil(canvas_width / cell_size_px)` by `ceil(canvas_height / cell_size_px)`.

The export canvas, not the preview canvas, is used for derived sizing. Preview must use the same logical grid as export.

### 10.4 3D grid sizing

- Version 1 supports cubic grids with `grid_size` from 8 through 80.
- The editor warns, but does not reject, sizes above 48 because render cost can rise sharply.
- Non-cubic 3D grids are deferred.

## 11. Rendering requirements

### 11.1 Canvas and compositing

- The canvas begins with a configurable solid RGB background.
- Each layer renders to an RGBA buffer at export dimensions.
- Disabled layers allocate no simulation or render work.
- Layer output is clipped to the canvas.
- Alpha compositing uses a documented straight- or premultiplied-alpha convention consistently.
- The final encoder frame is 8-bit RGB.

### 11.2 2D renderer

The 2D renderer supports:

- Nearest-neighbor cell rectangles with no smoothing.
- `fit` (show the full grid with letterboxing) and `cover` (fill and center-crop) layout.
- Horizontal and vertical alignment.
- Solid live-cell color or state gradient.
- Optional per-cell gap from 0 through 25% of cell size.
- Layer opacity.
- Trail amount from 0 through 1 and trail color.
- Visual fade rate in units per second; 0 means hard transitions.

Trail memory and fade interpolation are visual-only and never influence the automaton. Fade advances per video frame, making it smooth even when simulation steps are infrequent.

### 11.3 3D render styles

Two styles are required:

1. `isometric_voxel`: diamond-topped cuboids with top, left, right, and outline colors, based on the reference server.
2. `projected_voxel`: camera-rotated square voxel splats with perspective and a depth buffer, based on the Python proof of concept.

Common controls:

- Automatic voxel scale or fixed pixel scale.
- Voxel scale multiplier.
- Render all occupied voxels or surface voxels only.
- State, height, distance-from-center, or fixed palette coloring.
- Depth shading and background vignette toggles.
- Layer opacity and visual fade rate.

`surface_only` is the default for isometric grids large enough for hidden interior cells to affect performance. Surface detection uses the six orthogonal neighbors and respects the layer boundary mode.

### 11.4 Camera

The project has a default camera, and a 3D layer may override any camera field:

- Projection: `isometric`, `orthographic`, or `perspective` as supported by the selected renderer.
- Azimuth in degrees.
- Elevation in degrees.
- Zoom greater than 0.
- Perspective strength from 0 through 1.
- Rotation rate in degrees per second.
- Optional clockwise/counterclockwise direction through the sign of rotation rate.
- Pan X and Y in normalized canvas units.

Camera angle is derived from presentation time, not the number of calls to `render()`. Preview and export therefore agree at the same timestamp.

### 11.5 Visual interpolation

With `fade_rate > 0`, each cell has a visual presence value from 0 through 1 that moves linearly toward its occupied/unoccupied target by `fade_rate * frame_delta_seconds`, clamped at the target. A fading-out cell retains its last state color. With `fade_rate == 0`, visual presence follows the grid immediately.

## 12. Project file format

### 12.1 General rules

- UTF-8 JSON.
- Recommended suffix: `.cav.json`.
- Top-level `schema_version` is required.
- Unknown keys are validation errors by default.
- IDs must match `^[a-z][a-z0-9_-]{0,63}$` and be unique.
- Colors use `#RRGGBB` or explicit three-element integer arrays; saved projects normalize to `#RRGGBB`.
- Paths in a project are resolved relative to the project file, except the CLI `--output` override.
- Saving from the editor is atomic.

### 12.2 Canonical example

```json
{
  "schema_version": 1,
  "project": {
    "name": "Crystal over Life",
    "seed": 7
  },
  "output": {
    "path": "renders/crystal-life.mp4",
    "width": 1920,
    "height": 1080,
    "fps": 30,
    "duration_seconds": 12,
    "codec": "h264",
    "crf": 18,
    "encoder_preset": "medium"
  },
  "holds": {
    "start_seconds": 0.5,
    "end_seconds": 1.0,
    "rotate_camera_at_end": true
  },
  "canvas": {
    "background": "#0d1117"
  },
  "camera": {
    "projection": "perspective",
    "azimuth_deg": 30,
    "elevation_deg": 28,
    "zoom": 1.0,
    "perspective_strength": 0.35,
    "rotation_deg_per_second": 12,
    "pan_x": 0,
    "pan_y": 0
  },
  "layers": [
    {
      "id": "life_bg",
      "name": "Life background",
      "enabled": true,
      "dimension": "2d",
      "z_index": 0,
      "opacity": 0.18,
      "step_interval_ms": 80,
      "simulation": {
        "mode": "outer_totalistic",
        "grid": { "cell_size_px": 8, "boundary": "wrap" },
        "rule": { "preset": "life" },
        "initial": { "type": "random", "density": 0.3 }
      },
      "render": {
        "style": "cells",
        "color": "#00ffaa",
        "layout": "cover",
        "fade_rate": 0,
        "trail": 0.75,
        "trail_color": "#124c3b"
      }
    },
    {
      "id": "crystal_fg",
      "name": "Crystal foreground",
      "enabled": true,
      "dimension": "3d",
      "z_index": 10,
      "opacity": 1,
      "step_interval_ms": 180,
      "simulation": {
        "mode": "outer_totalistic",
        "grid": { "grid_size": 48, "boundary": "fixed" },
        "rule": { "preset": "crystal" },
        "initial": { "type": "catalog_default" }
      },
      "render": {
        "style": "projected_voxel",
        "palette": "crystal",
        "color_by": "distance",
        "voxel_scale": "auto",
        "surface_only": true,
        "fade_rate": 6
      }
    }
  ]
}
```

### 12.3 Rule union

A rule is exactly one of:

```json
{ "preset": "life" }
```

or:

```json
{
  "notation": "B3/S23/C2",
  "neighborhood": "moore"
}
```

The preset supplies neighborhood and state count. A custom rule must explicitly select its neighborhood.

### 12.4 Render metadata

Alongside `output.mp4`, a successful render writes `output.render.json` containing:

- SHA-256 of the normalized project configuration.
- Application version and schema version.
- Start and completion timestamps.
- Actual frame count, fps, width, height, and duration.
- Codec settings.
- PRNG algorithm and master seed.
- Per-layer rule, grid size, and final live-cell count.
- Total render time.

Metadata creation can be disabled from the CLI, but is enabled by default.

## 13. Native desktop editor UX

The authoritative layout and interaction design for the native editor is
defined in [`native-ui-design.md`](native-ui-design.md). That design adapts the
reference Web UI's canvas, Explorer, scene library, and scene editor workflows
to native Qt without reproducing its browser/server architecture.

### 13.1 Launch and project flow

Running `ca-video` or `ca-video gui [PROJECT.cav.json]` starts the PySide6 desktop editor. No server or network listener is created.

The main window uses `QMainWindow` with a central preview and dockable or resizable tool areas. Its default editor mode has a layer pane on the left, the 16:9 preview and transport in the center, and a contextual inspector on the right. A preview-only mode hides editor chrome and may be made full-screen. The application has:

- Project actions: New, Open, Save, Save As.
- Native file dialogs for projects, RLE input, rendered video destinations, and still-frame destinations.
- Output controls: resolution, fps, duration, quality, and destination.
- A central 16:9 preview canvas.
- Preview controls: Run/Pause, Step, Reset, jump-to-time, and preview quality.
- A layer list with visibility, type, selection, duplicate, reorder, and delete controls.
- A property inspector with Layer and Project tabs and context-sensitive, collapsible sections.
- A validation/results panel.
- A Render button and render-job progress view.
- Unsaved-change indication and confirmation before destructive New, Open, or Close operations.

Required layout:

- Left: layer list and add, duplicate, reorder, enable, and delete actions.
- Center: preview canvas and transport controls.
- Right: project or selected-layer property inspector.
- Bottom: validation messages, render progress, cancellation, and diagnostics.

The UI must remain usable at 1280×720 and must restore sensible window geometry without reopening off-screen.

The useful visual language and interaction patterns of the reference Web UI
are retained: a dark canvas-focused workspace, restrained teal accents,
categorized rules and palettes, contextual fields, compact statistics, and
immediate preview feedback. The reference's separate browser pages are not
copied literally:

- Canvas becomes preview-only mode.
- Explorer becomes the main editor workspace.
- Scenes becomes native New/Open/Open Recent and reusable presets.
- Scene editing becomes the project and selected-layer inspector.
- MIDI channels become ordered automaton layers.

MIDI channel numbers, event types and filters, target-channel routing,
collisions, destroy/control events, mutation chance, generations-per-event,
and server load actions have no native UI equivalent in version 1.

### 13.2 Preview behavior

- Preview uses the same simulation and render implementation as export.
- Preview rasterization is independent of export settings. Version 1 renders
  preview frames at no more than 640×360 and samples them at 30 preview ticks
  per second; smaller exports are not enlarged for preview.
- Preview and export use the same logical grids and simulation step intervals.
  Preview ticks sample exact rational presentation times, so a layer reaches
  the same generation at the same timestamp regardless of export fps.
- Export resolution and fps are used only by offline rendering. Changing them
  must not cause the editor to allocate full-resolution preview frames or run
  the preview timer at the export frame rate.
- NumPy RGB/RGBA frames are bridged to Qt using `QImage` with explicit ownership and row-stride handling; the UI must not retain a view onto a reused or freed array.
- Reset reproduces frame zero exactly.
- Jump-to-time resets and simulates forward deterministically. Version 1 need not cache arbitrary snapshots.
- The HUD shows presentation time, per-layer generation, live cell count,
  density, grid size, selected rule, preview raster/fps, and export raster/fps.
- Editing a simulation-affecting property resets the affected layer after confirmation when the preview has advanced.
- Editing only a render property updates without resetting simulation where safe.

### 13.3 Render jobs

- Only one export job runs per app process in version 1.
- Progress reports frames completed and total frames.
- Cancellation is cooperative and checked at least once per frame.
- The UI remains responsive during render.
- Full renders run in a `QThread` or `QThreadPool` worker, never on the Qt GUI thread.
- Worker progress, completion, cancellation, and failure reach widgets through Qt signals using queued cross-thread delivery.
- A render job receives an immutable normalized project snapshot; subsequent editor changes do not alter a running render.
- Validation must succeed before a render starts.
- Errors display a concise message in the UI and retain detailed diagnostics in a log file.

## 14. Command-line interface

Required commands:

```text
ca-video [PROJECT.cav.json]
ca-video gui [PROJECT.cav.json]
ca-video validate PROJECT.cav.json
ca-video render PROJECT.cav.json [--output FILE.mp4] [--overwrite]
ca-video frame PROJECT.cav.json --time SECONDS --output FILE.png
ca-video catalogs [--dimension 2d|3d] [--json]
ca-video migrate LEGACY.json --output PROJECT.cav.json
```

CLI behavior:

- Success exits 0.
- Project or validation errors exit 2.
- Render/encoder failures exit 3.
- Cancellation exits 130.
- Logs go to stderr; machine-readable results can be requested with `--json` where applicable.
- `render` never overwrites an existing file without `--overwrite`.
- `ca-video` with no subcommand is equivalent to `ca-video gui`.

## 15. Legacy migration

### 15.1 Python proof-of-concept JSON

`ca-video migrate` supports the current single-automaton proof-of-concept format and maps:

- `dimensions`, `size`, `rule`, `birth`, `survive`, `states`, `neighborhood`, and `wrap` into one layer.
- `seed` into the project master seed.
- `init` into layer initialization.
- `video` dimensions, fps, output, steps-per-frame, and holds into the new output/timing model.
- `colors` and `camera` into the corresponding render settings.

Because the old format defines `steps` rather than duration, migration computes a proposed duration and emits a warning showing the calculation. The migrated file must pass normal validation before rendering.

### 15.2 Reference server scenes

Version 1 does not parse or execute `.js` scene modules. Rule definitions, palette definitions, and useful sample layouts are ported into Python-owned catalogs and project presets. A later, explicit conversion tool may accept a restricted JSON export from the server, but channels, events, collisions, and mutations would be dropped with warnings.

## 16. Recommended architecture

```text
src/ca_video/
  cli.py
  config/
    models.py
    schema.py
    migrate.py
  catalogs/
    rules_2d.json
    rules_3d.json
    palettes_3d.json
    projects/
  simulation/
    engine.py
    outer_totalistic.py
    wolfram.py
    neighborhoods.py
    initialization.py
  rendering/
    renderer_2d.py
    renderer_3d_iso.py
    renderer_3d_projected.py
    camera.py
    compositor.py
  encoding/
    ffmpeg.py
    jobs.py
  ui/
    application.py
    main_window.py
    preview_widget.py
    layer_model.py
    property_inspector.py
    render_worker.py
    dialogs.py
    resources/
tests/
  unit/
  integration/
  golden/
```

Responsibilities:

- Configuration models parse, normalize, and validate but do not simulate.
- Simulation engines operate on NumPy arrays and return state without drawing.
- Renderers consume immutable simulation snapshots and presentation time.
- The compositor knows layer order and alpha but not automaton rules.
- The encoder accepts an iterator/stream of RGB frames.
- UI and CLI call the same application services.
- Qt widgets stay on the GUI thread; render jobs run in workers with explicit progress and cancellation state.
- The Qt adapter converts application-service results into models, signals, and images without embedding simulation logic in widgets.
- The native UI opens no listening socket and has no HTTP dependency.

Recommended dependency direction:

```text
UI / CLI -> application services -> simulation + rendering -> encoder
                         \-> configuration + catalogs
```

No simulation, rendering, configuration, or encoding module may import PySide6. Only the `ui` package and the top-level GUI entry point depend on Qt. This keeps the CLI and headless tests usable without constructing a `QApplication`.

## 17. Validation and error handling

Validation occurs before allocating large grids or launching FFmpeg. It checks:

- Schema version and unknown fields.
- Output aspect ratio, dimensions, fps, duration, and integral frame counts.
- Hold durations.
- Unique layer IDs and valid layer ordering fields.
- Dimension/mode-specific fields and mutually exclusive fields.
- Grid limits and estimated memory.
- Rule counts against neighborhood capacity.
- Palette and preset references.
- Initialization geometry and RLE parseability.
- Readability of input files and writability of the output parent directory.
- Availability of an H.264-capable FFmpeg encoder.

Errors use a structure such as:

```json
{
  "code": "invalid_rule_count",
  "path": "layers[1].simulation.rule.notation",
  "message": "Birth count 9 exceeds the 2D Moore maximum of 8."
}
```

Warnings do not block render and include high-cost grid settings, an initially empty automaton, fully transparent layers, and likely early extinction.

## 18. Performance and resource behavior

- Frame production is streaming and bounded; memory must not scale with video duration.
- The app may keep current/next simulation grids, interpolation buffers, layer frame buffers, and one composite frame.
- A normal render must not leak memory per frame.
- 3D surface extraction and projection should operate only on occupied/surface coordinates when that is faster than dense iteration.
- Neighbor counting should use vectorized NumPy operations or an equivalently tested optimized path.
- The editor estimates render complexity before starting and labels it Low, Medium, High, or Very High.
- Version 1 has no strict render-time SLA because cost depends heavily on grid density, 3D style, layers, fps, and hardware.
- A benchmark command or test records elapsed time and peak resident memory for standard 720p and 1080p fixtures so regressions are visible.

Standard stress fixture:

- 1920×1080, 30 fps, 60 seconds.
- One 240×135 2D layer and one 48³ surface-only 3D layer.
- Frame stream completes without exceeding 2 GiB peak resident memory on the development reference machine.

## 19. Testing strategy

### 19.1 Unit tests

- Rule parser, including empty survival sets and multi-digit ranges.
- Every neighborhood and both boundary modes.
- Two-state and Generations transitions.
- Wolfram truth tables and scrolling.
- Every initializer with fixed seeds.
- Random stream independence by layer ID.
- Camera transformation and time-based rotation.
- Fade/trail progression.
- Alpha composition and stable ordering.
- Configuration validation and migrations.

### 19.2 Golden tests

Store small lossless PNG or NumPy-array fixtures for selected frames from:

- 2D Life.
- Brian's Brain.
- 2D Wolfram rule 30.
- 3D `445` in isometric mode.
- 3D crystal in projected mode.
- A mixed 2D-background/3D-foreground project.

Golden fixtures use tiny grids and canvases. Updating them requires an explicit review command; ordinary tests never rewrite expected output.

### 19.3 Integration tests

- Render a short MP4 and probe it with FFprobe.
- Verify codec, pixel format, exact dimensions, fps, frame count, and duration.
- Verify cancellation leaves no replacement output.
- Verify overwrite protection.
- Render the same fixture twice and compare decoded frame hashes.
- Exercise editor validation and a complete background render job through Qt's application layer.
- Smoke-test native Qt Widgets startup through the `xcb` platform plugin on the supported Linux target.
- Smoke-test `QImage` creation at 1920×1080 and graceful preview fallback when an OpenGL context is unavailable.

## 20. Version 1 acceptance criteria

Version 1 is complete when all of the following are true:

1. A user can create, save, reopen, preview, and render a project through the native PySide6 editor without starting a browser or local server.
2. A project can contain at least one 2D and one 3D layer with independent step intervals and ordered alpha composition.
3. All required 2D rules, 3D rules, 3D palettes, and Wolfram rules 0–255 are selectable.
4. Custom valid B/S/C rules work in 2D and 3D with Moore or von Neumann neighborhoods.
5. Random, centered, sphere/disc, explicit-cell, catalog-default, and 2D RLE initialization work as specified.
6. Both isometric and projected 3D styles render correctly.
7. Fade, trail, opacity, palette, color-by, camera, and camera-rotation controls affect preview and export consistently.
8. The app exports a valid `yuv420p` H.264 MP4 at 1920×1080, 30 fps, and exactly 60 seconds for the stress fixture.
9. No accepted project can exceed 1920×1080, 16:9, or 60 seconds.
10. Re-rendering the same project produces identical decoded RGB frame hashes.
11. Rendering is streamed and the stress fixture stays below the specified memory ceiling.
12. CLI validation, single-frame rendering, full rendering, migration, cancellation, and overwrite protection work.
13. No MIDI, HTTP event, SSE, event timeline, collision, or dynamic mutation subsystem is required for acceptance.

## 21. Implementation phases

### Phase 1 — Core and CLI

- Package skeleton and configuration models.
- Rule/palette catalogs.
- Deterministic 2D, 3D, and Wolfram simulation.
- 2D and both 3D renderers.
- Layer compositor.
- FFmpeg streaming export.
- Validation, metadata, CLI, and proof-of-concept migration.
- Unit, golden, and headless integration tests.

### Phase 2 — Native desktop editor

- Three-pane PySide6 editor shell and preview-only mode as specified in
  `docs/native-ui-design.md`.
- Project New/Open/Save/Save As, atomic writes, recent files, and dirty-state
  handling.
- Catalog-driven, context-sensitive project and layer inspectors.
- `QImage` preview surface, transport, zoom, and compact HUD.
- Layer management, visual controls, and deterministic reset/update behavior.
- Qt worker-based render jobs, progress, cancellation, and diagnostics.

### Phase 3 — Hardening

- 1080p/60-second stress validation.
- Performance profiling and targeted optimization.
- Project schema compatibility tests.
- Example projects and end-user documentation.
- Packaging for a one-command local install and launch.

## 22. Deferred decisions

These do not block Phase 1:

- Whether a later release should import a restricted JSON export from `midi-ca-server-2`.
- Whether future versions should support audio muxing.
- Whether future versions should add blend modes beyond normal source-over.
- Whether preview snapshot caching is worthwhile for faster scrubbing.
- Whether non-cubic 3D grids should be supported.
- Whether a future event/timeline subsystem is desirable; version 1 must not pre-emptively build one.
