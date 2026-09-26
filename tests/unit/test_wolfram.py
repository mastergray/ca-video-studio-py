import numpy as np  # Describe exact elementary cellular-automata fixtures

from ca_video.simulation.wolfram import WolframEngine  # Exercise scrolling Wolfram histories


def test_every_rule_uses_standard_elementary_truth_table() -> None:
    for ruleNumber in range(256):
        engine = WolframEngine(3, 1, ruleNumber)
        for pattern in range(8):
            row = np.array(
                [(pattern >> 2) & 1, (pattern >> 1) & 1, pattern & 1],
                dtype=np.uint8,
            )
            assert engine._nextRow(row)[1] == (ruleNumber >> pattern) & 1


def test_rule_30_prefills_expected_history() -> None:
    engine = WolframEngine(7, 4, 30)

    expected = np.array(
        [
            [0, 0, 0, 1, 0, 0, 0],
            [0, 0, 1, 1, 1, 0, 0],
            [0, 1, 1, 0, 0, 1, 0],
            [1, 1, 0, 1, 1, 1, 1],
        ],
        dtype=np.uint8,
    )
    np.testing.assert_array_equal(engine.grid, expected)
    assert engine.generation == 0


def test_step_scrolls_and_appends_next_row() -> None:
    engine = WolframEngine(7, 4, 30)
    previous = engine.grid.copy()
    expectedBottom = engine._nextRow(engine.row)

    engine.step()

    np.testing.assert_array_equal(engine.grid[:-1], previous[1:])
    np.testing.assert_array_equal(engine.grid[-1], expectedBottom)
    assert engine.generation == 1


def test_random_initial_row_is_seeded_deterministically() -> None:
    first = WolframEngine(32, 8, 90, "random", 0.4, 123)
    second = WolframEngine(32, 8, 90, "random", 0.4, 123)
    different = WolframEngine(32, 8, 90, "random", 0.4, 124)

    np.testing.assert_array_equal(first.grid, second.grid)
    assert not np.array_equal(first.grid, different.grid)


def test_explicit_bits_are_centered_in_the_starting_row() -> None:
    engine = WolframEngine(9, 1, 0, "bits", bits=(1, 0, 1))

    np.testing.assert_array_equal(
        engine.grid[0],
        np.array([0, 0, 0, 1, 0, 1, 0, 0, 0], dtype=np.uint8),
    )


def test_blank_engine_has_no_visible_cells() -> None:
    engine = WolframEngine.blank(9, 5, 30)

    assert engine.liveCount == 0
    assert engine.ruleNumber == 30
