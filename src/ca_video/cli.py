from __future__ import annotations  # Enable forward references in type annotations

import argparse  # Parse command-line operations and options
import sys  # Read arguments and report errors
from pathlib import Path  # Parse explicit output paths

from ca_video import __version__  # Report the installed application version
from ca_video.config.models import ConfigError, loadProject  # Load validated projects
from ca_video.encoding.ffmpeg import (  # Render projects and classify render failures
    RenderCancelled,
    RenderError,
    renderProject,
)

COMMANDS = {"gui", "validate", "render"}


# :: VOID -> argumentParser
# Builds the command-line parser and supported subcommands
def buildParser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ca-video",
        description="Cellular automata video generator",
    )
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command")

    gui = subparsers.add_parser("gui", help="open the native editor")
    gui.add_argument("project", nargs="?", help="optional .cav.json project")

    validate = subparsers.add_parser("validate", help="validate a project")
    validate.add_argument("project")

    render = subparsers.add_parser("render", help="render a project to MP4")
    render.add_argument("project")
    render.add_argument("--output", type=Path)
    render.add_argument("--overwrite", action="store_true")
    return parser


# :: [STRING] -> [STRING]
# Makes the native GUI the default command
def _normalizeArgv(argv: list[str]) -> list[str]:
    if not argv:
        return ["gui"]
    if argv[0].startswith("-") or argv[0] in COMMANDS:
        return argv
    return ["gui", *argv]


# :: [STRING]? -> INT
# Executes a GUI, validation, or render command
def main(argv: list[str] | None = None) -> int:
    sourceArgs = list(sys.argv[1:] if argv is None else argv)
    args = buildParser().parse_args(_normalizeArgv(sourceArgs))
    try:
        if args.command == "gui":
            from ca_video.ui.application import runGui  # Delay Qt initialization for headless commands

            return runGui(args.project)
        if args.command == "validate":
            project = loadProject(args.project)
            print(
                f"valid: {project.name} — {project.output.width}x{project.output.height}, "
                f"{project.output.fps} fps, {project.output.totalFrames} frames"
            )
            return 0
        if args.command == "render":
            project = loadProject(args.project)

            # :: INT, INT -> NONE
            # Writes in-place frame progress for an active CLI render
            def showProgress(done: int, total: int) -> None:
                print(f"\rframe {done}/{total}", end="", flush=True)

            result = renderProject(
                project,
                args.output,
                overwrite=args.overwrite,
                progress=showProgress,
            )
            print(f"\nwrote {result}")
            return 0
    except KeyboardInterrupt:
        print("\ncancelled", file=sys.stderr)
        return 130
    except RenderCancelled:
        print("render cancelled", file=sys.stderr)
        return 130
    except ConfigError as error:
        print(f"configuration error: {error}", file=sys.stderr)
        return 2
    except RenderError as error:
        print(f"render error: {error}", file=sys.stderr)
        return 3
    return 0
