import numpy as np

from mrfdpf.fdpf_core import C0, solve_field
from mrfdpf.geometry import Scene, Source, Wall
from mrfdpf.grid import build_grid


def test_wall_rasterization_sets_material():
    scene = Scene(width=1.0, height=1.0, walls=[Wall(0.5, 0.0, 0.5, 1.0, material="concrete", thickness=0.1)])
    grid = build_grid(scene, dx=0.02)

    iy, ix = grid.xy_to_index(0.5, 0.5)
    assert grid.eps_r[iy, ix] > 1.5  # inside the wall

    iy_air, ix_air = grid.xy_to_index(0.1, 0.5)
    assert grid.eps_r[iy_air, ix_air] == 1.0  # far from any wall


def test_metal_wall_creates_shadow():
    freq_hz = 2.4e9
    dx = (C0 / freq_hz) / 15

    source = Source(x=0.3, y=0.5)
    target_xy = (0.7, 0.5)

    scene_wall = Scene(
        width=1.0,
        height=1.0,
        walls=[Wall(0.5, 0.0, 0.5, 1.0, material="metal", thickness=0.02)],
        sources=[source],
    )
    scene_free = Scene(width=1.0, height=1.0, walls=[], sources=[source])

    grid_wall = build_grid(scene_wall, dx)
    grid_free = build_grid(scene_free, dx)

    iy0, ix0 = grid_wall.xy_to_index(source.x, source.y)
    iy_t, ix_t = grid_wall.xy_to_index(*target_xy)

    E_wall = solve_field(grid_wall.eps_r, grid_wall.sigma, freq_hz, dx, iy0, ix0)
    E_free = solve_field(grid_free.eps_r, grid_free.sigma, freq_hz, dx, iy0, ix0)

    mag_wall = np.abs(E_wall[iy_t, ix_t])
    mag_free = np.abs(E_free[iy_t, ix_t])

    assert mag_wall < 0.3 * mag_free, (
        f"expected strong shadowing behind metal wall, got wall={mag_wall:.3e} "
        f"free={mag_free:.3e}"
    )
