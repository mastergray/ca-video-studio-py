# CA Video Generator

Native Python/PySide6 application for previewing and exporting deterministic cellular-automata videos.

The current vertical slice supports one deterministic 2D Conway's Life layer, native preview controls, and H.264 MP4 export through FFmpeg. The broader product is defined in [`docs/ca-video-spec.md`](docs/ca-video-spec.md).

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
