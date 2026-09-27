from __future__ import annotations  # Enable forward references in type annotations

import math  # Rotate and tilt voxel coordinates

import numpy as np  # Project, shade, and depth-buffer voxel sprites
from numpy.typing import NDArray  # Describe voxel grids and RGBA layers

from ca_video.catalogs.rules_3d import Palette3D  # Derive projected color gradients
from ca_video.config.models import CameraConfig  # Read validated camera settings

RGBAFrame = NDArray[np.float32]


# Rasterizes camera-projected voxels with a per-pixel depth buffer
class ProjectedRenderer3D:

    # CONSTRUCTOR :: INT, INT, palette3D, cameraConfig, FLOAT, INT, BOOL, STRING, STRING, BOOL, BOOL, INT -> projectedRenderer3D
    # Creates a deterministic projected voxel renderer
    def __init__(
        self,
        width: int,
        height: int,
        palette: Palette3D,
        camera: CameraConfig,
        opacity: float = 1,
        voxelScale: int = 0,
        surfaceOnly: bool = True,
        boundary: str = "fixed",
        colorBy: str = "fixed",
        depthShading: bool = True,
        vignette: bool = False,
        states: int = 2,
    ) -> None:
        self._width = width
        self._height = height
        self._palette = palette
        self._camera = camera
        self._opacity = opacity
        self._voxelScale = voxelScale
        self._surfaceOnly = surfaceOnly
        self._boundary = boundary
        self._colorBy = colorBy
        self._depthShading = depthShading
        self._vignette = vignette
        self._states = states
        self._colorLut = self._buildColorLut()

    # :: grid3D, FLOAT, presence?, grid3D? -> rgbaFrame
    # Projects occupied voxels at an exact presentation timestamp
    def renderLayer(
        self,
        grid: NDArray[np.uint8],
        presentationSeconds: float = 0,
        presence: NDArray[np.float32] | None = None,
        displayGrid: NDArray[np.uint8] | None = None,
    ) -> RGBAFrame:
        if grid.ndim != 3 or len(set(grid.shape)) != 1:
            raise ValueError("projected 3D renderer requires a cubic voxel grid")
        layer = self._emptyLayer()
        visualGrid = displayGrid if displayGrid is not None else grid
        coordinates = self._visibleCoordinates(visualGrid, presence)
        if not len(coordinates):
            return layer

        zValues = coordinates[:, 0]
        yValues = coordinates[:, 1]
        xValues = coordinates[:, 2]
        gridSize = grid.shape[0]
        center = (gridSize - 1) / 2
        points = np.stack((xValues, yValues, zValues), axis=1).astype(np.float32) - center
        radius = max(1.0, math.sqrt(3 * gridSize**2) / 2)
        colors = self._voxelColors(visualGrid, coordinates, points, radius)
        alphas = (
            presence[zValues, yValues, xValues]
            if presence is not None
            else np.ones(len(coordinates), dtype=np.float32)
        )

        azimuth = math.radians(
            self._camera.azimuthDeg + self._camera.rotationDegPerSecond * presentationSeconds
        )
        elevation = math.radians(self._camera.elevationDeg)
        cosineAzimuth, sineAzimuth = math.cos(azimuth), math.sin(azimuth)
        rotatedX = points[:, 0] * cosineAzimuth - points[:, 1] * sineAzimuth
        rotatedY = points[:, 0] * sineAzimuth + points[:, 1] * cosineAzimuth
        cosineElevation, sineElevation = math.cos(elevation), math.sin(elevation)
        depth = rotatedY * cosineElevation + points[:, 2] * sineElevation
        vertical = -rotatedY * sineElevation + points[:, 2] * cosineElevation

        perspective = self._camera.perspectiveStrength if self._camera.projection == "perspective" else 0
        perspectiveScale = (
            1 / (1 + perspective * depth / (radius * 2))
            if perspective
            else np.ones_like(depth)
        )
        basePixels = min(self._width, self._height) * 0.46 * self._camera.zoom / radius
        originX = self._width / 2 + self._camera.panX * self._width / 2
        originY = self._height / 2 + self._camera.panY * self._height / 2
        screenX = originX + rotatedX * basePixels * perspectiveScale
        screenY = originY - vertical * basePixels * perspectiveScale
        sizes = (
            np.full(len(depth), self._voxelScale, dtype=np.int64)
            if self._voxelScale
            else np.maximum(1, np.round(basePixels * perspectiveScale * 0.92)).astype(np.int64)
        )

        depthRange = float(np.ptp(depth))
        normalizedDepth = (depth - depth.min()) / max(1e-6, depthRange)
        shading = 1.05 - 0.55 * normalizedDepth if self._depthShading else np.ones_like(depth)
        self._rasterize(layer, screenX, screenY, sizes, depth, colors, shading, alphas)
        return layer

    # :: VOID -> rgbaFrame
    # Creates a transparent layer with an optional edge vignette
    def _emptyLayer(self) -> RGBAFrame:
        layer = np.zeros((self._height, self._width, 4), dtype=np.float32)
        if not self._vignette:
            return layer
        yValues, xValues = np.mgrid[0 : self._height, 0 : self._width]
        distance = np.sqrt(
            ((xValues - self._width / 2) / (self._width / 2)) ** 2
            + ((yValues - self._height / 2) / (self._height / 2)) ** 2
        )
        layer[..., 3] = np.clip((distance - 0.25) * 0.18, 0, 0.18) * self._opacity
        return layer

    # :: grid3D, presence? -> array
    # Extracts occupied or six-neighbor surface voxel coordinates
    def _visibleCoordinates(
        self,
        grid: NDArray[np.uint8],
        presence: NDArray[np.float32] | None = None,
    ) -> NDArray[np.int64]:
        occupied = presence > 1e-6 if presence is not None else grid > 0
        if not self._surfaceOnly:
            return np.argwhere(occupied)
        solid = presence >= 0.5 if presence is not None else occupied
        neighbors = self._orthogonalOccupancy(solid)
        return np.argwhere(occupied & (neighbors < 6))

    # :: array -> array
    # Counts occupied orthogonal neighbors with the configured boundary
    def _orthogonalOccupancy(self, occupied: NDArray[np.bool_]) -> NDArray[np.uint8]:
        offsets = ((-1, 0, 0), (1, 0, 0), (0, -1, 0), (0, 1, 0), (0, 0, -1), (0, 0, 1))
        counts = np.zeros(occupied.shape, dtype=np.uint8)
        if self._boundary == "wrap":
            for offset in offsets:
                counts += np.roll(occupied, offset, axis=(0, 1, 2))
            return counts
        padded = np.pad(occupied, 1, mode="constant")
        gridSize = occupied.shape[0]
        for deltaZ, deltaY, deltaX in offsets:
            startZ, startY, startX = deltaZ + 1, deltaY + 1, deltaX + 1
            counts += padded[
                startZ : startZ + gridSize,
                startY : startY + gridSize,
                startX : startX + gridSize,
            ]
        return counts

    # :: grid3D, array, array, FLOAT -> array
    # Maps voxel state or position into the selected palette gradient
    def _voxelColors(
        self,
        grid: NDArray[np.uint8],
        coordinates: NDArray[np.int64],
        points: NDArray[np.float32],
        radius: float,
    ) -> NDArray[np.float32]:
        if self._colorBy == "fixed":
            return np.tile(np.asarray(self._palette.top, dtype=np.float32), (len(coordinates), 1))
        if self._colorBy == "height":
            values = coordinates[:, 0] / max(1, grid.shape[0] - 1)
        elif self._colorBy == "distance":
            values = np.linalg.norm(points, axis=1) / radius
        else:
            states = grid[coordinates[:, 0], coordinates[:, 1], coordinates[:, 2]]
            values = states / max(1, self._states - 1)
        indices = np.round(np.clip(values, 0, 1) * 255).astype(np.int64)
        return self._colorLut[indices]

    # :: rgbaFrame, array, array, array, array, array, array, array -> NONE
    # Writes beveled square sprites using nearest-depth-per-pixel selection
    def _rasterize(
        self,
        layer: RGBAFrame,
        screenX: NDArray[np.float32],
        screenY: NDArray[np.float32],
        sizes: NDArray[np.int64],
        depth: NDArray[np.float32],
        colors: NDArray[np.float32],
        shading: NDArray[np.float32],
        alphas: NDArray[np.float32],
    ) -> None:
        maximumSize = int(sizes.max())
        halfSizes = sizes // 2
        startX = np.round(screenX).astype(np.int64) - halfSizes
        startY = np.round(screenY).astype(np.int64) - halfSizes
        pixelParts: list[NDArray[np.int64]] = []
        depthParts: list[NDArray[np.float32]] = []
        colorParts: list[NDArray[np.float32]] = []
        alphaParts: list[NDArray[np.float32]] = []
        for offsetY in range(maximumSize):
            for offsetX in range(maximumSize):
                included = (offsetX < sizes) & (offsetY < sizes)
                if not included.any():
                    continue
                pixelX = startX[included] + offsetX
                pixelY = startY[included] + offsetY
                inBounds = (
                    (pixelX >= 0)
                    & (pixelX < self._width)
                    & (pixelY >= 0)
                    & (pixelY < self._height)
                )
                if not inBounds.any():
                    continue
                includedSizes = sizes[included][inBounds]
                bevel = np.ones(len(includedSizes), dtype=np.float32)
                if maximumSize >= 4:
                    bevel[(offsetX == 0) | (offsetY == 0)] = 1.18
                    bevel[(offsetX == includedSizes - 1) | (offsetY == includedSizes - 1)] = 0.62
                    bevel *= 1.08 - 0.16 * (offsetX + offsetY) / np.maximum(1, 2 * (includedSizes - 1))
                pixelParts.append(pixelY[inBounds] * self._width + pixelX[inBounds])
                depthParts.append(depth[included][inBounds])
                brightness = (shading[included][inBounds] * bevel)[:, None]
                colorParts.append(colors[included][inBounds] * brightness)
                alphaParts.append(alphas[included][inBounds])
        if not pixelParts:
            return
        pixels = np.concatenate(pixelParts)
        depths = np.concatenate(depthParts)
        colorsByPixel = np.concatenate(colorParts)
        alphasByPixel = np.concatenate(alphaParts)
        order = np.argsort(depths, kind="stable")
        pixels = pixels[order]
        colorsByPixel = colorsByPixel[order]
        alphasByPixel = alphasByPixel[order]
        _, first = np.unique(pixels, return_index=True)
        flatLayer = layer.reshape(-1, 4)
        flatLayer[pixels[first], :3] = colorsByPixel[first].clip(0, 255)
        flatLayer[pixels[first], 3] = self._opacity * alphasByPixel[first]

    # :: VOID -> array
    # Interpolates the face palette into a 256-color projected gradient
    def _buildColorLut(self) -> NDArray[np.float32]:
        stops = np.asarray(
            (self._palette.outline, self._palette.right, self._palette.left, self._palette.top),
            dtype=np.float32,
        )
        positions = np.linspace(0, len(stops) - 1, 256)
        lower = np.floor(positions).astype(np.int64)
        upper = np.minimum(lower + 1, len(stops) - 1)
        fraction = (positions - lower)[:, None]
        return stops[lower] * (1 - fraction) + stops[upper] * fraction
