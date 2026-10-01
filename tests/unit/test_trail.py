import numpy as np  # Build logical grids and inspect deterministic trail decay

from ca_video_studio_py.rendering.trail import TrailState  # Exercise 2D live-cell history


def test_trail_retention_uses_reference_thirty_fps_timing() -> None:
    initial = np.zeros((2, 2), dtype=np.uint8)
    initial[0, 0] = 1
    trail = TrailState(initial)
    changed = np.zeros((2, 2), dtype=np.uint8)

    trail.transition(changed, 0.5, 0)
    trail.sample(0.5, 1 / 30)

    assert trail.values[0, 0] == 0.5
    trail.sample(0.5, 2 / 30)
    assert trail.values[0, 0] == 0.25


def test_trail_zero_clears_dead_history_and_new_live_cells_start_full() -> None:
    initial = np.zeros((2, 2), dtype=np.uint8)
    initial[0, 0] = 1
    trail = TrailState(initial)
    changed = np.zeros((2, 2), dtype=np.uint8)
    changed[1, 1] = 1

    trail.transition(changed, 0, 1)

    assert trail.values[0, 0] == 0
    assert trail.values[1, 1] == 1
