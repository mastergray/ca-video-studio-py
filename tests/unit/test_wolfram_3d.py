import numpy as np  # Compare extruded elementary histories

from ca_video.simulation.wolfram import WolframEngine  # Build matching 2D history rows
from ca_video.simulation.wolfram_3d import WolframEngine3D  # Exercise reference-style extrusion


def test_wolfram_3d_prefills_2d_history_through_centered_depth_band() -> None:
    history2D = WolframEngine(16, 16, 30)
    history3D = WolframEngine3D(16, 30, extrusionDepth=4)

    for yIndex in range(6, 10):
        np.testing.assert_array_equal(history3D.grid[:, yIndex, :], history2D.grid)
    assert np.count_nonzero(history3D.grid[:, :6, :]) == 0
    assert np.count_nonzero(history3D.grid[:, 10:, :]) == 0


def test_wolfram_3d_shift_and_append_matches_reference_sequence() -> None:
    engine = WolframEngine3D(12, 90, extrusionDepth=3)
    previous = engine.grid.copy()
    sourceRow = engine.row.copy()
    left = np.roll(sourceRow, 1)
    right = np.roll(sourceRow, -1)
    patterns = (left << 2) | (sourceRow << 1) | right
    expected = ((90 >> patterns) & 1).astype(np.uint8)

    engine.step()

    np.testing.assert_array_equal(engine.grid[:-1], previous[1:])
    for yIndex in range(4, 7):
        np.testing.assert_array_equal(engine.grid[-1, yIndex], expected)
    assert engine.generation == 1


def test_wolfram_3d_random_source_row_is_seeded() -> None:
    first = WolframEngine3D(18, 122, "random", 0.4, 123, extrusionDepth=4)
    second = WolframEngine3D(18, 122, "random", 0.4, 123, extrusionDepth=4)
    different = WolframEngine3D(18, 122, "random", 0.4, 124, extrusionDepth=4)

    np.testing.assert_array_equal(first.grid, second.grid)
    assert not np.array_equal(first.grid, different.grid)
