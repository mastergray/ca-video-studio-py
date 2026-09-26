import json  # Parse FFprobe output
import subprocess  # Inspect the rendered MP4 stream

from ca_video.config.models import defaultProject  # Create a valid render fixture
from ca_video.encoding.ffmpeg import renderProject  # Exercise the real FFmpeg pipeline


def test_short_mp4_has_expected_stream(tmp_path) -> None:
    project = defaultProject(tmp_path)
    project = project.withOutputPath(tmp_path / "unused.mp4")
    outputConfig = project.output.withOverrides(
        width=320,
        height=180,
        fps=10,
        durationSeconds=0.5,
        encoderPreset="ultrafast",
    )
    project = type(project)(
        project.schemaVersion,
        project.name,
        project.seed,
        outputConfig,
        project.canvasBackground,
        project.layer,
        project.baseDir,
    )
    output = tmp_path / "test.mp4"
    renderProject(project, output)

    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_name,width,height,pix_fmt,nb_frames",
            "-of",
            "json",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    stream = json.loads(probe.stdout)["streams"][0]
    assert stream == {
        "codec_name": "h264",
        "width": 320,
        "height": 180,
        "pix_fmt": "yuv420p",
        "nb_frames": "5",
    }
