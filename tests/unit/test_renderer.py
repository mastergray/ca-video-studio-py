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
