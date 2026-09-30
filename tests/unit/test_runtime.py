import numpy as np  # Compare rendered frame buffers

from ca_video.config.models import defaultProject, parseProject  # Create deterministic test projects
from ca_video.services.runtime import ProjectRuntime  # Exercise shared preview/export timing
from ca_video.simulation.life_3d import OuterTotalisticEngine3D  # Identify voxel runtime layers
from ca_video.simulation.wolfram import WolframEngine  # Identify Wolfram runtime layers
from ca_video.simulation.wolfram_3d import WolframEngine3D  # Identify extruded Wolfram layers


def test_runtime_is_deterministic_and_frame_zero_is_initial_state() -> None:
    project = defaultProject()
    first = ProjectRuntime(project)
    second = ProjectRuntime(project)

    frame_a = first.renderFrame(37)
    frame_b = second.renderFrame(37)

    assert first.engine.generation == 12
    np.testing.assert_array_equal(frame_a, frame_b)


def test_reset_reproduces_initial_frame() -> None:
    runtime = ProjectRuntime(defaultProject())
    initial = runtime.renderFrame(0).copy()
    runtime.renderFrame(60)
    runtime.reset()
    np.testing.assert_array_equal(runtime.renderFrame(0), initial)


def test_layers_advance_on_independent_clocks() -> None:
    data = defaultProject().toDict()
    second = defaultProject().toDict()["layers"][0]
    second["id"] = "slow"
    second["step_interval_ms"] = 200
    data["layers"].append(second)
    runtime = ProjectRuntime(parseProject(data))

    runtime.renderFrame(3)

    assert runtime.engineForLayer(0).generation == 1
    assert runtime.engineForLayer(1).generation == 0


def test_higher_z_index_composites_last() -> None:
    data = defaultProject().toDict()
    data["output"].update({"width": 320, "height": 180})
    data["canvas"]["background"] = "#000000"
    top = data["layers"][0]
    top.update({"id": "top", "z_index": 1, "opacity": 1})
    top["simulation"]["grid"] = {"size": [16, 9], "boundary": "fixed"}
    top["simulation"]["initial"] = {"type": "cells", "origin": "absolute", "cells": [[8, 4]]}
    top["render"].update({"color": "#ff0000", "layout": "fit"})
    bottom = defaultProject().toDict()["layers"][0]
    bottom.update({"id": "bottom", "z_index": 0, "opacity": 1})
    bottom["simulation"]["grid"] = {"size": [16, 9], "boundary": "fixed"}
    bottom["simulation"]["initial"] = {"type": "cells", "origin": "absolute", "cells": [[8, 4]]}
    bottom["render"].update({"color": "#0000ff", "layout": "fit"})
    data["layers"] = [top, bottom]

    frame = ProjectRuntime(parseProject(data)).renderFrame(0)

    np.testing.assert_array_equal(frame[90, 170], np.array([255, 0, 0], dtype=np.uint8))


def test_layer_seed_override_is_independent_of_project_seed() -> None:
    firstData = defaultProject().toDict()
    firstData["layers"][0]["seed"] = 12345
    secondData = defaultProject().toDict()
    secondData["project"]["seed"] = 999
    secondData["layers"][0]["seed"] = 12345

    first = ProjectRuntime(parseProject(firstData))
    second = ProjectRuntime(parseProject(secondData))

    np.testing.assert_array_equal(first.engine.grid, second.engine.grid)


def test_derived_layer_seed_changes_with_project_seed() -> None:
    firstData = defaultProject().toDict()
    secondData = defaultProject().toDict()
    secondData["project"]["seed"] = firstData["project"]["seed"] + 1

    first = ProjectRuntime(parseProject(firstData))
    second = ProjectRuntime(parseProject(secondData))

    assert not np.array_equal(first.engine.grid, second.engine.grid)


def test_preview_runtime_uses_capped_raster_size() -> None:
    data = defaultProject().toDict()
    data["output"].update({"width": 1920, "height": 1080})
    project = parseProject(data)

    preview = ProjectRuntime(project, (640, 360)).renderAtTick(0, 30)
    export = ProjectRuntime(project).renderFrame(0)

    assert preview.shape == (360, 640, 3)
    assert export.shape == (1080, 1920, 3)


def test_preview_and_export_match_generation_at_same_time() -> None:
    data = defaultProject().toDict()
    data["output"]["fps"] = 60
    project = parseProject(data)
    previewRuntime = ProjectRuntime(project, (640, 360))
    exportRuntime = ProjectRuntime(project, (640, 360))

    previewFrame = previewRuntime.renderAtTick(3, 30)
    exportFrame = exportRuntime.renderFrame(6)

    assert previewRuntime.engine.generation == 1
    assert exportRuntime.engine.generation == 1
    np.testing.assert_array_equal(previewFrame, exportFrame)


def test_state_gradient_is_deterministic_across_preview_and_export_clocks() -> None:
    data = defaultProject().toDict()
    data["output"]["fps"] = 60
    layer = data["layers"][0]
    layer["step_interval_ms"] = 100
    layer["simulation"]["rule"] = {
        "notation": "B2/S/C4",
        "neighborhood": "moore",
    }
    layer["render"].update(
        {
            "color_mode": "state_gradient",
            "gradient": ["#ff4020", "#7040c0", "#102050"],
        }
    )
    project = parseProject(data)
    previewRuntime = ProjectRuntime(project, (640, 360))
    exportRuntime = ProjectRuntime(project, (640, 360))

    previewFrame = previewRuntime.renderAtTick(9, 30)
    exportFrame = exportRuntime.renderFrame(18)

    assert previewRuntime.engine.generation == 3
    assert exportRuntime.engine.generation == 3
    np.testing.assert_array_equal(previewFrame, exportFrame)


def test_fade_progress_is_deterministic_across_sampling_intervals() -> None:
    data = defaultProject().toDict()
    layer = data["layers"][0]
    layer["step_interval_ms"] = 1000
    layer["simulation"]["grid"] = {"size": [8, 8], "boundary": "fixed"}
    layer["simulation"]["initial"] = {
        "type": "cells",
        "origin": "absolute",
        "cells": [[2, 3], [3, 3], [4, 3]],
    }
    layer["render"]["fade_rate"] = 0.7
    project = parseProject(data)
    direct = ProjectRuntime(project, (80, 80))
    sampled = ProjectRuntime(project, (80, 80))

    directFrame = direct.renderAtTick(3, 2)
    sampled.renderAtTick(1, 2)
    sampled.renderAtTick(2, 2)
    sampledFrame = sampled.renderAtTick(3, 2)
    presence = direct._fadeStates[layer["id"]].presence

    assert presence[3, 2] == np.float32(0.65)
    assert presence[2, 3] == np.float32(0.35)
    assert presence[3, 3] == 1
    assert direct.engine.generation == 1
    np.testing.assert_array_equal(directFrame, sampledFrame)
    np.testing.assert_array_equal(presence, sampled._fadeStates[layer["id"]].presence)


def test_fade_state_resets_with_the_simulation() -> None:
    data = defaultProject().toDict()
    data["layers"][0]["render"]["fade_rate"] = 2
    project = parseProject(data)
    runtime = ProjectRuntime(project, (320, 180))
    initial = runtime.renderAtTick(0, 30)

    runtime.renderAtTick(20, 30)
    reset = runtime.renderAtTick(0, 30)

    np.testing.assert_array_equal(reset, initial)


def test_trail_decay_is_deterministic_across_preview_and_export_rates() -> None:
    data = defaultProject().toDict()
    layer = data["layers"][0]
    layer["step_interval_ms"] = 1000
    layer["simulation"]["grid"] = {"size": [8, 8], "boundary": "fixed"}
    layer["simulation"]["initial"] = {
        "type": "cells",
        "origin": "absolute",
        "cells": [[2, 3], [3, 3], [4, 3]],
    }
    layer["render"].update({"trail": 0.83, "trail_color": "#2f5fb0"})
    project = parseProject(data)
    direct = ProjectRuntime(project, (80, 80))
    sampled = ProjectRuntime(project, (80, 80))

    directFrame = direct.renderAtTick(45, 30)
    for tickIndex in range(1, 91):
        sampledFrame = sampled.renderAtTick(tickIndex, 60)
    directTrail = direct._trailStates[layer["id"]].values
    sampledTrail = sampled._trailStates[layer["id"]].values

    np.testing.assert_allclose(directTrail[3, 2], 0.83**15)
    assert directTrail[2, 3] == 1
    np.testing.assert_array_equal(directTrail, sampledTrail)
    np.testing.assert_array_equal(directFrame, sampledFrame)


def test_wolfram_and_outer_totalistic_layers_share_independent_timing() -> None:
    data = defaultProject().toDict()
    wolfram = defaultProject().toDict()["layers"][0]
    wolfram.update({"id": "rule_30", "name": "Rule 30", "step_interval_ms": 200})
    wolfram["simulation"] = {
        "mode": "wolfram_2d",
        "grid": {"size": [80, 45], "boundary": "wrap"},
        "rule": {"number": 30},
        "initial": {"type": "single_center"},
    }
    data["layers"].append(wolfram)
    runtime = ProjectRuntime(parseProject(data), (320, 180))

    frame = runtime.renderAtTick(6, 30)

    assert runtime.engineForLayer(0).generation == 2
    assert runtime.engineForLayer(1).generation == 1
    assert isinstance(runtime.engineForLayer(1), WolframEngine)
    assert frame.shape == (180, 320, 3)


def test_shape_pixel_offset_uses_export_scale_for_preview_and_export() -> None:
    data = defaultProject().toDict()
    data["layers"][0]["simulation"]["initial"] = {
        "type": "disc",
        "density": 1,
        "radius": 1,
        "offset_px": [40, -20],
    }
    project = parseProject(data)
    previewRuntime = ProjectRuntime(project, (320, 180))
    exportRuntime = ProjectRuntime(project)

    np.testing.assert_array_equal(previewRuntime.engine.grid, exportRuntime.engine.grid)
    assert previewRuntime.engine.grid[39, 89] == 1
    assert previewRuntime._shapeOffsetCells(project.layer) == (10, -5)
    assert previewRuntime._nearestCellOffset(2, 160, 640) == 1
    assert previewRuntime._nearestCellOffset(-2, 160, 640) == -1
    assert previewRuntime._nearestCellOffset(1, 160, 640) == 0


def test_shape_pixel_offset_uses_cover_layout_scale() -> None:
    data = defaultProject().toDict()
    data["layers"][0]["simulation"]["grid"] = {"size": [100, 100], "boundary": "wrap"}
    data["layers"][0]["simulation"]["initial"] = {
        "type": "center_block",
        "density": 1,
        "radius": 1,
        "offset_px": [64, 64],
    }
    data["layers"][0]["render"]["layout"] = "cover"
    project = parseProject(data)
    runtime = ProjectRuntime(project, (320, 180))

    assert runtime._shapeOffsetCells(project.layer) == (10, 10)


def test_mixed_2d_and_3d_layers_render_on_independent_clocks() -> None:
    data = defaultProject().toDict()
    data["layers"].append(
        {
            "id": "voxel_crystal",
            "name": "Voxel Crystal",
            "dimension": "3d",
            "z_index": 1,
            "step_interval_ms": 200,
            "opacity": 0.75,
            "simulation": {
                "mode": "outer_totalistic",
                "grid": {"grid_size": 16, "boundary": "fixed"},
                "rule": {"preset": "crystal"},
                "initial": {"type": "cross"},
            },
            "render": {
                "style": "isometric_voxel",
                "palette": "crystal",
                "surface_only": True,
            },
        }
    )
    runtime = ProjectRuntime(parseProject(data), (320, 180))

    frame = runtime.renderAtTick(6, 30)

    assert runtime.engineForLayer(0).generation == 2
    assert runtime.engineForLayer(1).generation == 1
    assert isinstance(runtime.engineForLayer(1), OuterTotalisticEngine3D)
    assert frame.shape == (180, 320, 3)
    assert frame.max() > 0


def test_projected_camera_matches_at_equal_preview_and_export_times() -> None:
    data = defaultProject().toDict()
    data["output"]["fps"] = 60
    data["layers"][0] = {
        "id": "projected",
        "name": "Projected",
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
            "color_by": "height",
            "surface_only": True,
            "camera": {"rotation_deg_per_second": 90},
        },
    }
    project = parseProject(data)
    previewRuntime = ProjectRuntime(project, (320, 180))
    exportRuntime = ProjectRuntime(project, (320, 180))

    previewFrame = previewRuntime.renderAtTick(15, 30)
    exportFrame = exportRuntime.renderFrame(30)

    np.testing.assert_array_equal(previewFrame, exportFrame)


def test_wolfram_3d_uses_shared_timing_and_renderer_pipeline() -> None:
    data = defaultProject().toDict()
    data["layers"][0] = {
        "id": "wolfram_3d",
        "name": "Wolfram 3D",
        "dimension": "3d",
        "step_interval_ms": 200,
        "simulation": {
            "mode": "wolfram_3d_extruded",
            "grid": {"grid_size": 20, "boundary": "fixed"},
            "rule": {"number": 30},
            "initial": {"type": "single_center"},
            "extrusion_depth": 5,
        },
        "render": {
            "style": "projected_voxel",
            "palette": "wolfram3d",
            "surface_only": True,
        },
    }
    runtime = ProjectRuntime(parseProject(data), (320, 180))

    frame = runtime.renderAtTick(6, 30)

    assert isinstance(runtime.engine, WolframEngine3D)
    assert runtime.engine.generation == 1
    assert frame.shape == (180, 320, 3)
    assert frame.max() > 0
