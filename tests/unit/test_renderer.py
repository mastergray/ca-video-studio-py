import numpy as np  # Build source grids and inspect RGB output

from ca_video.rendering.renderer_2d import Renderer2D, scaledGridSize  # Exercise exact-size 2D rendering


def test_renderer_produces_exact_rgb_dimensions() -> None:
    grid = np.zeros((9, 16), dtype=np.uint8)
    grid[4, 8] = 1
    renderer = Renderer2D(320, 180, (0, 0, 0), (255, 128, 64))
    frame = renderer.render(grid)

    assert frame.shape == (180, 320, 3)
    assert frame.dtype == np.uint8
    assert frame.max() == 255


def test_scaled_grid_size_matches_fit_and_cover_geometry() -> None:
    assert scaledGridSize(640, 360, 100, 100, "fit") == (360, 360)
    assert scaledGridSize(640, 360, 100, 100, "cover") == (640, 640)


def test_renderer_applies_logical_fade_presence_to_alpha() -> None:
    grid = np.zeros((9, 16), dtype=np.uint8)
    grid[4, 8] = 1
    presence = np.zeros_like(grid, dtype=np.float32)
    presence[4, 8] = 0.25
    renderer = Renderer2D(16, 9, (0, 0, 0), (255, 128, 64))

    layer = renderer.renderLayer(grid, presence=presence, displayGrid=grid)

    assert layer[4, 8, 3] == 0.25


def test_renderer_draws_dead_cell_history_in_trail_color() -> None:
    grid = np.zeros((9, 16), dtype=np.uint8)
    trail = np.zeros_like(grid, dtype=np.float32)
    trail[4, 8] = 0.5
    renderer = Renderer2D(
        16,
        9,
        (0, 0, 0),
        (255, 255, 255),
        trailColor=(20, 80, 160),
    )

    layer = renderer.renderLayer(grid, trailValues=trail)

    np.testing.assert_array_equal(layer[4, 8, :3], np.array([20, 80, 160]))
    assert layer[4, 8, 3] == 0.5


def test_trail_appears_beneath_cells_that_are_still_fading_out() -> None:
    grid = np.zeros((9, 16), dtype=np.uint8)
    displayGrid = np.zeros_like(grid)
    displayGrid[4, 8] = 1
    presence = np.zeros_like(grid, dtype=np.float32)
    presence[4, 8] = 0.25
    trail = np.zeros_like(grid, dtype=np.float32)
    trail[4, 8] = 0.5
    renderer = Renderer2D(
        16,
        9,
        (0, 0, 0),
        (255, 255, 255),
        trailColor=(20, 80, 160),
    )

    layer = renderer.renderLayer(
        grid,
        presence=presence,
        displayGrid=displayGrid,
        trailValues=trail,
    )

    expectedColor = (
        np.array([255, 255, 255]) * 0.25
        + np.array([20, 80, 160]) * 0.375
    ) / 0.625
    np.testing.assert_allclose(layer[4, 8, :3], expectedColor)
    assert layer[4, 8, 3] == 0.625
