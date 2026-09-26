import numpy as np  # Compare rendered frame buffers

from ca_video.config.models import defaultProject, parseProject  # Create deterministic test projects
from ca_video.services.runtime import ProjectRuntime  # Exercise shared preview/export timing


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
