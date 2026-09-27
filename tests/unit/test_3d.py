import numpy as np  # Build voxel fixtures and compare deterministic results
import pytest  # Assert invalid 3D rule limits

from ca_video.catalogs.rules_3d import (  # Verify reference 3D catalogs
    getPalette3D,
    getRule3D,
    palette3DCatalog,
    rule3DCatalog,
)
from ca_video.config.models import CameraConfig  # Configure projected camera tests
from ca_video.rendering.renderer_3d import Renderer3D  # Rasterize voxel fixtures
from ca_video.rendering.renderer_3d_projected import ProjectedRenderer3D  # Test camera projection
from ca_video.simulation.initialization_3d import initializeGrid3D  # Build seeded voxel grids
from ca_video.simulation.life_3d import OuterTotalisticEngine3D  # Evolve 3D rules
from ca_video.simulation.rules import parseRule  # Validate 3D B/S limits


def test_reference_3d_catalog_is_complete_and_parseable() -> None:
    expected = {
        "445", "amoeba", "builder", "architecture", "fortress", "platter", "cubic", "pyroclastic",
        "pulse", "blinker3d", "slow_blob", "electrified", "coral", "crystal", "diamoeba3d", "spiky",
        "shell", "symmetrica", "snowflake", "growth", "creep", "coral_wall", "sticks", "pyro", "cloud",
        "bugs3d", "fireworks", "chaos3d", "nova", "static3d", "slow_decay", "maze3d",
    }

    assert {entry.key for entry in rule3DCatalog()} == expected
    assert expected < {palette.key for palette in palette3DCatalog()}
    for key in expected:
        assert getRule3D(key).rule.states == 2
        assert getPalette3D(key).top


def test_3d_rule_parser_supports_multi_digit_counts_and_limits() -> None:
    rule = parseRule("B13-15/S12,16,26", "moore", 3)
    assert rule.birth == (13, 14, 15)
    assert rule.survival == (12, 16, 26)
    assert rule.notation == "B13,14,15/S12,16,26"
    with pytest.raises(ValueError, match="maximum of 6"):
        parseRule("B7/S1", "von_neumann", 3)


def test_3d_initializers_are_seeded_and_use_zyx_storage() -> None:
    first = initializeGrid3D(12, "random", 0.25, 2, 99)
    second = initializeGrid3D(12, "random", 0.25, 2, 99)
    explicit = initializeGrid3D(9, "cells", 1, 1, 0, ((1, -1, 2),), "center")

    np.testing.assert_array_equal(first, second)
    assert explicit[6, 3, 5] == 1
    assert explicit.sum() == 1


def test_geometric_3d_seed_offsets_clip_or_wrap_at_volume_edges() -> None:
    shifted = initializeGrid3D(9, "single", 1, 1, 0, offsetCells=(2, -1, 3))
    clipped = initializeGrid3D(5, "cross", 1, 1, 0, boundary="fixed", offsetCells=(2, 2, 2))
    wrapped = initializeGrid3D(5, "cross", 1, 1, 0, boundary="wrap", offsetCells=(2, 2, 2))

    assert shifted[7, 3, 6] == 1
    assert shifted.sum() == 1
    assert clipped.sum() == 4
    assert wrapped.sum() == 7
    assert wrapped[4, 4, 0] == 1
    assert wrapped[4, 0, 4] == 1
    assert wrapped[0, 4, 4] == 1


def test_3d_engine_counts_moore_and_von_neumann_neighbors() -> None:
    grid = np.zeros((5, 5, 5), dtype=np.uint8)
    grid[2, 2, 2] = 1
    moore = OuterTotalisticEngine3D(grid, parseRule("B1/S", "moore", 3), "fixed")
    vonNeumann = OuterTotalisticEngine3D(grid, parseRule("B1/S", "von_neumann", 3), "fixed")

    moore.step()
    vonNeumann.step()

    assert moore.liveCount == 26
    assert vonNeumann.liveCount == 6


def test_3d_renderer_produces_transparent_exact_size_layer() -> None:
    grid = np.zeros((8, 8, 8), dtype=np.uint8)
    grid[4, 4, 4] = 1
    renderer = Renderer3D(320, 180, getPalette3D("445"))
    layer = renderer.renderLayer(grid)

    assert layer.shape == (180, 320, 4)
    assert layer.dtype == np.float32
    assert layer[..., 3].max() == 1
    assert np.count_nonzero(layer[..., 3]) > 0


def test_3d_renderers_apply_per_voxel_fade_presence() -> None:
    grid = np.zeros((8, 8, 8), dtype=np.uint8)
    grid[4, 4, 4] = 1
    presence = np.zeros_like(grid, dtype=np.float32)
    presence[4, 4, 4] = 0.25
    isometric = Renderer3D(160, 90, getPalette3D("445"))
    projected = ProjectedRenderer3D(160, 90, getPalette3D("445"), CameraConfig())

    isometricLayer = isometric.renderLayer(grid, presence=presence, displayGrid=grid)
    projectedLayer = projected.renderLayer(grid, presence=presence, displayGrid=grid)

    assert 0 < isometricLayer[..., 3].max() < 0.3
    assert projectedLayer[..., 3].max() == 0.25


def test_projected_renderer_is_timestamp_driven_and_exact_size() -> None:
    grid = np.zeros((12, 12, 12), dtype=np.uint8)
    grid[4:8, 5, 4:8] = 1
    camera = CameraConfig(rotationDegPerSecond=45)
    renderer = ProjectedRenderer3D(320, 180, getPalette3D("crystal"), camera, colorBy="height")

    initial = renderer.renderLayer(grid, 0)
    rotated = renderer.renderLayer(grid, 1)

    assert initial.shape == (180, 320, 4)
    assert initial.dtype == np.float32
    assert initial[..., 3].max() == 1
    assert not np.array_equal(initial, rotated)
    np.testing.assert_array_equal(renderer.renderLayer(grid, 1), rotated)


def test_projected_renderer_keeps_nearest_voxel_per_pixel() -> None:
    camera = CameraConfig(
        projection="orthographic",
        azimuthDeg=0,
        elevationDeg=0,
        rotationDegPerSecond=0,
    )
    renderer = ProjectedRenderer3D(
        160,
        90,
        getPalette3D("crystal"),
        camera,
        voxelScale=8,
        surfaceOnly=False,
        colorBy="state",
        depthShading=False,
        states=3,
    )
    nearOnly = np.zeros((9, 9, 9), dtype=np.uint8)
    nearOnly[4, 2, 4] = 1
    overlapped = nearOnly.copy()
    overlapped[4, 6, 4] = 2

    np.testing.assert_array_equal(renderer.renderLayer(overlapped), renderer.renderLayer(nearOnly))
