import numpy as np  # Build and compare deterministic test grids

from ca_video.simulation.life import LifeEngine  # Exercise Life transitions


def test_blinker_oscillates_with_fixed_boundaries() -> None:
    initial = np.zeros((5, 5), dtype=np.uint8)
    initial[2, 1:4] = 1
    engine = LifeEngine(initial, "fixed")

    engine.step()
    expected = np.zeros((5, 5), dtype=np.uint8)
    expected[1:4, 2] = 1
    np.testing.assert_array_equal(engine.grid, expected)

    engine.step()
    np.testing.assert_array_equal(engine.grid, initial)


def test_random_initialization_is_deterministic() -> None:
    first = LifeEngine.init(32, 18, 0.3, 42)
    second = LifeEngine.init(32, 18, 0.3, 42)
    np.testing.assert_array_equal(first.grid, second.grid)
