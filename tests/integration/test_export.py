import json  # Parse FFprobe output
import subprocess  # Inspect the rendered MP4 stream

from ca_video.config.models import defaultProject, parseProject  # Create valid render fixtures
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


def test_wolfram_project_exports_through_shared_pipeline(tmp_path) -> None:
    data = defaultProject(tmp_path).toDict()
    data["output"].update(
        {
            "width": 320,
            "height": 180,
            "fps": 10,
            "duration_seconds": 0.2,
            "encoder_preset": "ultrafast",
        }
    )
    data["layers"][0]["simulation"] = {
        "mode": "wolfram_2d",
        "grid": {"size": [80, 45], "boundary": "wrap"},
        "rule": {"number": 30},
        "initial": {"type": "single_center"},
    }
    output = tmp_path / "wolfram.mp4"
    renderProject(parseProject(data, tmp_path), output)

    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,nb_frames",
            "-of",
            "json",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(probe.stdout)["streams"][0] == {
        "width": 320,
        "height": 180,
        "nb_frames": "2",
    }


def test_3d_project_exports_through_shared_pipeline(tmp_path) -> None:
    data = defaultProject(tmp_path).toDict()
    data["output"].update(
        {
            "width": 320,
            "height": 180,
            "fps": 10,
            "duration_seconds": 0.2,
            "encoder_preset": "ultrafast",
        }
    )
    data["layers"][0] = {
        "id": "crystal",
        "name": "Crystal",
        "dimension": "3d",
        "simulation": {
            "mode": "outer_totalistic",
            "grid": {"grid_size": 16, "boundary": "fixed"},
            "rule": {"preset": "crystal"},
            "initial": {"type": "cross"},
        },
        "render": {
            "style": "projected_voxel",
            "palette": "crystal",
            "color_by": "distance",
            "surface_only": True,
            "camera": {"rotation_deg_per_second": 30},
        },
    }
    output = tmp_path / "crystal.mp4"
    renderProject(parseProject(data, tmp_path), output)

    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,nb_frames",
            "-of",
            "json",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(probe.stdout)["streams"][0] == {
        "width": 320,
        "height": 180,
        "nb_frames": "2",
    }


def test_wolfram_3d_project_exports_through_shared_pipeline(tmp_path) -> None:
    data = defaultProject(tmp_path).toDict()
    data["output"].update(
        {
            "width": 320,
            "height": 180,
            "fps": 10,
            "duration_seconds": 0.2,
            "encoder_preset": "ultrafast",
        }
    )
    data["layers"][0] = {
        "id": "wolfram_3d",
        "name": "Wolfram 3D",
        "dimension": "3d",
        "simulation": {
            "mode": "wolfram_3d_extruded",
            "grid": {"grid_size": 20, "boundary": "fixed"},
            "rule": {"number": 30},
            "initial": {"type": "single_center"},
            "extrusion_depth": 5,
        },
        "render": {
            "style": "isometric_voxel",
            "palette": "wolfram3d",
            "surface_only": True,
        },
    }
    output = tmp_path / "wolfram-3d.mp4"
    renderProject(parseProject(data, tmp_path), output)

    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,nb_frames",
            "-of",
            "json",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(probe.stdout)["streams"][0] == {
        "width": 320,
        "height": 180,
        "nb_frames": "2",
    }
