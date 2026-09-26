import numpy as np  # Compare rendered frame buffers

from ca_video.config.models import defaultProject  # Create deterministic test projects
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
