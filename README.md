# CA Video Generator

Native Python/PySide6 application for previewing and exporting deterministic cellular-automata videos.

The current editable milestone supports ordered deterministic 2D and 3D layers
with independent rules and timing. It includes the complete reference 2D and 3D
rule catalogs, custom 2D B/S/C rules, elementary Wolfram rules 0–255 rendered as
scrolling histories, isometric surface voxels, and camera-projected voxels with
perspective, time-based rotation, positional coloring, and depth buffering.
Global and optional per-layer seeds, multiple initial-condition types,
native project editing and persistence, preview controls, mixed-dimensional
composition, and H.264 MP4 export through FFmpeg share one deterministic
pipeline. The broader product is defined in
[`docs/ca-video-spec.md`](docs/ca-video-spec.md); the desktop layout is defined
in [`docs/native-ui-design.md`](docs/native-ui-design.md).

The editor preview is capped at 640×360 and 30 fps. Export resolution and frame
rate are applied only during offline video rendering.

## Development setup

Requirements:

- Python 3.11
- FFmpeg with `libx264`
- On Ubuntu/X11: `libxcb-cursor0`

```bash
uv sync
uv run ca-video
```

Open the example project:

```bash
uv run ca-video gui examples/life.cav.json
```

Open the layered example:

```bash
uv run ca-video gui examples/layered-life.cav.json
```

Open the Wolfram Rule 30 example:

```bash
uv run ca-video gui examples/wolfram-rule-30.cav.json
```

Open the isometric 3D 445 example:

```bash
uv run ca-video gui examples/isometric-445.cav.json
```

Open the camera-projected crystal example:

```bash
uv run ca-video gui examples/projected-crystal.cav.json
```

Validate or render without the GUI:

```bash
uv run ca-video validate examples/life.cav.json
uv run ca-video render examples/life.cav.json --output renders/life.mp4
```

Run tests:

```bash
uv run ruff check src tests
uv run pytest
```

Development and repository conventions are documented in [`CONTRIBUTING.md`](CONTRIBUTING.md).
