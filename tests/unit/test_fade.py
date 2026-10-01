import numpy as np  # Build logical grids and inspect interpolation buffers

from ca_video_studio_py.rendering.fade import FadeState  # Exercise visual-only cell presence


def test_fade_state_moves_linearly_and_retains_last_live_state() -> None:
    initial = np.zeros((2, 2), dtype=np.uint8)
    initial[0, 0] = 2
    fade = FadeState(initial)
    changed = np.zeros((2, 2), dtype=np.uint8)
    changed[0, 1] = 1

    fade.transition(changed, 2, 0)
    fade.sample(changed, 2, 0.25)

    np.testing.assert_allclose(fade.presence, np.array([[0.5, 0.5], [0, 0]]))
    assert fade.displayGrid[0, 0] == 2
    assert fade.displayGrid[0, 1] == 1

    fade.sample(changed, 2, 0.5)
    np.testing.assert_array_equal(fade.presence, np.array([[0, 1], [0, 0]]))


def test_zero_fade_rate_snaps_to_current_grid() -> None:
    initial = np.ones((2, 2, 2), dtype=np.uint8)
    fade = FadeState(initial)
    changed = np.zeros_like(initial)
    changed[1, 1, 1] = 1

    fade.transition(changed, 0, 0)

    np.testing.assert_array_equal(fade.presence, changed.astype(np.float32))
