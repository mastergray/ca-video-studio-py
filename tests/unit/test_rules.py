import numpy as np  # Build state-transition fixtures
import pytest  # Assert invalid rule failures

from ca_video_studio_py.catalogs.rules_2d import ruleCatalog  # Verify the required rule collection
from ca_video_studio_py.simulation.life import OuterTotalisticEngine  # Exercise general automata
from ca_video_studio_py.simulation.rules import parseRule  # Parse custom notation


def test_required_2d_catalog_is_complete() -> None:
    assert {entry.key for entry in ruleCatalog()} == {
        "life",
        "highlife",
        "longlife",
        "life34",
        "seeds",
        "brian",
        "starwars",
        "replicator",
        "morley",
        "two_by_two",
        "daynight",
        "diamoeba",
        "anneal",
        "coag",
        "stains",
        "maze",
        "mazectric",
        "walled",
        "vote",
        "vote45",
    }


def test_generations_rule_advances_through_decay_states() -> None:
    grid = np.zeros((3, 3), dtype=np.uint8)
    grid[1, 1] = 1
    engine = OuterTotalisticEngine(grid, parseRule("B/S/C3"), "fixed")

    engine.step()
    assert engine.grid[1, 1] == 2
    assert engine.liveCount == 0
    engine.step()
    assert engine.grid[1, 1] == 0


def test_von_neumann_counts_only_orthogonal_neighbors() -> None:
    grid = np.zeros((5, 5), dtype=np.uint8)
    grid[2, 2] = 1
    engine = OuterTotalisticEngine(grid, parseRule("B1/S", "von_neumann"), "fixed")
    engine.step()
    assert engine.liveCount == 4
    assert engine.grid[1, 1] == 0


def test_rule_rejects_counts_beyond_neighborhood() -> None:
    with pytest.raises(ValueError, match="maximum of 4"):
        parseRule("B5/S", "von_neumann")
