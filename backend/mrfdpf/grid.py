"""Rasterization of a Scene onto a uniform grid of complex permittivity.

Each wall is painted onto the cells it overlaps using a one-cell-wide
smoothstep transition (poor man's anti-aliasing): a cell fully inside the
wall's thickness gets the wall material, a cell fully outside stays air,
and cells straddling the wall edge get a linear blend of (eps_r, sigma).
Overlapping walls keep the highest-coverage material per cell rather than
accumulating, which is a reasonable approximation for thin sub-cell
features and avoids double-counting where walls meet.
"""

from __future__ import annotations

import numpy as np

from .geometry import Scene, Wall
from .materials import get_material


class Grid:
    def __init__(self, width: float, height: float, dx: float):
        self.dx = dx
        self.nx = max(2, int(np.ceil(width / dx)) + 1)
        self.ny = max(2, int(np.ceil(height / dx)) + 1)
        self.eps_r = np.ones((self.ny, self.nx))
        self.sigma = np.zeros((self.ny, self.nx))
        self._coverage = np.zeros((self.ny, self.nx))

    def xy_to_index(self, x: float, y: float) -> tuple[int, int]:
        ix = int(round(x / self.dx))
        iy = int(round(y / self.dx))
        ix = min(max(ix, 0), self.nx - 1)
        iy = min(max(iy, 0), self.ny - 1)
        return iy, ix


def _point_segment_distance(px, py, x1, y1, x2, y2):
    dxs, dys = x2 - x1, y2 - y1
    seg_len2 = dxs * dxs + dys * dys
    if seg_len2 == 0:
        return np.hypot(px - x1, py - y1)
    t = ((px - x1) * dxs + (py - y1) * dys) / seg_len2
    t = np.clip(t, 0.0, 1.0)
    proj_x = x1 + t * dxs
    proj_y = y1 + t * dys
    return np.hypot(px - proj_x, py - proj_y)


def rasterize_wall(grid: Grid, wall: Wall) -> None:
    material = get_material(wall.material)
    half_t = wall.thickness / 2.0
    pad = grid.dx

    x_min = min(wall.x1, wall.x2) - half_t - pad
    x_max = max(wall.x1, wall.x2) + half_t + pad
    y_min = min(wall.y1, wall.y2) - half_t - pad
    y_max = max(wall.y1, wall.y2) + half_t + pad

    ix_min = max(0, int(np.floor(x_min / grid.dx)))
    ix_max = min(grid.nx - 1, int(np.ceil(x_max / grid.dx)))
    iy_min = max(0, int(np.floor(y_min / grid.dx)))
    iy_max = min(grid.ny - 1, int(np.ceil(y_max / grid.dx)))

    for iy in range(iy_min, iy_max + 1):
        y = iy * grid.dx
        for ix in range(ix_min, ix_max + 1):
            x = ix * grid.dx
            dist = _point_segment_distance(x, y, wall.x1, wall.y1, wall.x2, wall.y2)
            w = np.clip((half_t + grid.dx / 2 - dist) / grid.dx, 0.0, 1.0)
            if w <= 0.0:
                continue
            if w > grid._coverage[iy, ix]:
                grid._coverage[iy, ix] = w
                grid.eps_r[iy, ix] = (1 - w) * 1.0 + w * material.eps_r
                grid.sigma[iy, ix] = (1 - w) * 0.0 + w * material.sigma


def build_grid(scene: Scene, dx: float) -> Grid:
    grid = Grid(scene.width, scene.height, dx)
    for wall in scene.walls:
        rasterize_wall(grid, wall)
    return grid
