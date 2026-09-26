# CA Video Generator

Native Python/PySide6 application for previewing and exporting deterministic cellular-automata videos.

The current editable milestone supports ordered deterministic 2D layers with
independent rules and timing, the complete reference 2D rule catalog, custom
B/S/C rules, elementary Wolfram rules 0–255 rendered as scrolling histories,
global and optional per-layer seeds, multiple initial-condition types, native
project editing and persistence, preview controls, and H.264 MP4 export through
FFmpeg. The broader product is defined in
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
