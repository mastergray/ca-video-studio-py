import numpy as np  # Compare initialized cell grids
import pytest  # Assert malformed pattern failures

from ca_video.simulation.initialization import initializeGrid, parseRle  # Exercise initializer variants


def test_disc_and_center_block_are_deterministic() -> None:
    first = initializeGrid(21, 21, "disc", 0.5, 4, 99)
    second = initializeGrid(21, 21, "disc", 0.5, 4, 99)
    np.testing.assert_array_equal(first, second)

    block = initializeGrid(9, 9, "center_block", 1, 1, 1, (3, 5))
    assert int(block.sum()) == 15


def test_explicit_cells_wrap_deterministically() -> None:
    grid = initializeGrid(
        8,
        8,
        "cells",
        1,
        1,
        1,
        cells=((-1, -1), (8, 8)),
        origin="absolute",
        boundary="wrap",
    )
    assert grid[7, 7] == 1
    assert grid[0, 0] == 1


def test_rle_parser_reads_a_glider() -> None:
    pattern = parseRle("#N Glider\nx = 3, y = 3, rule = B3/S23\nbob$2bo$3o!")
    assert pattern.shape == (3, 3)
    assert int(pattern.sum()) == 5


def test_rle_parser_rejects_unsupported_symbols() -> None:
    with pytest.raises(ValueError, match="unsupported symbols"):
        parseRle("x = 2, y = 2\nAB!")
