from __future__ import annotations  # Enable forward references in type annotations

import os  # Atomically replace completed output files
import shutil  # Locate the FFmpeg executable
import subprocess  # Stream raw frames into FFmpeg
import uuid  # Create collision-resistant temporary output names
from collections.abc import Callable  # Describe progress and cancellation callbacks
from pathlib import Path  # Represent destination paths

from ca_video.config.models import ProjectConfig  # Read validated render settings
from ca_video.services.runtime import ProjectRuntime  # Produce deterministic RGB frames

ProgressCallback = Callable[[int, int], None]
CancelCallback = Callable[[], bool]


# Indicates that an output render failed
class RenderError(RuntimeError):
    pass


# Indicates that an output render was cancelled cooperatively
class RenderCancelled(RenderError):
    pass


# :: projectConfig, path?, BOOL, (INT, INT -> NONE)?, (VOID -> BOOL)? -> path
# Streams a project to an atomic H.264 MP4 output
def renderProject(
    project: ProjectConfig,
    destination: Path | None = None,
    *,
    overwrite: bool = False,
    progress: ProgressCallback | None = None,
    cancelled: CancelCallback | None = None,
) -> Path:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RenderError("ffmpeg was not found on PATH")

    output = (destination or project.outputPath()).expanduser().resolve()
    if output.suffix.lower() != ".mp4":
        raise RenderError("output path must end in .mp4")
    if output.exists() and not overwrite:
        raise RenderError(f"output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.stem}.{uuid.uuid4().hex}.part.mp4")

    settings = project.output
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostats",
        "-y",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-video_size",
        f"{settings.width}x{settings.height}",
        "-framerate",
        str(settings.fps),
        "-i",
        "-",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        settings.encoderPreset,
        "-crf",
        str(settings.crf),
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(temporary),
    ]

    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    runtime = ProjectRuntime(project)
    total = settings.totalFrames
    try:
        assert process.stdin is not None
        for frameIndex in range(total):
            if cancelled and cancelled():
                raise RenderCancelled("render cancelled")
            frame = runtime.renderFrame(frameIndex)
            process.stdin.write(frame.tobytes(order="C"))
            if progress:
                progress(frameIndex + 1, total)
        process.stdin.close()
        errorOutput = process.stderr.read().decode("utf-8", errors="replace") if process.stderr else ""
        returnCode = process.wait()
        if returnCode:
            raise RenderError(errorOutput.strip() or f"ffmpeg exited with status {returnCode}")
        os.replace(temporary, output)
        return output
    except BaseException:
        if process.stdin and not process.stdin.closed:
            process.stdin.close()
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        temporary.unlink(missing_ok=True)
        raise
