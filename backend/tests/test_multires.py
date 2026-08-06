"""Validate the multi-resolution (exact substructuring) solver against the
direct single-resolution reference on identical scenes.

Because the substructuring in multires.py is algebraically exact (a
reordering + Schur-complement elimination of the very same operator
fdpf_core builds), agreement with solve_field should be near machine
precision -- this is a much stronger check than a fuzzy physical
tolerance, and a regression here means an actual bug in the tiling /
elimination logic, not an approximation trade-off.
"""

import time

import numpy as np

from mrfdpf.fdpf_core import C0, solve_field
from mrfdpf.geometry import Scene, Source, Wall
from mrfdpf.grid import build_grid
from mrfdpf.multires import solve_field_multires


def test_multires_matches_single_resolution_free_space():
    freq_hz = 2.4e9
    dx = (C0 / freq_hz) / 15
    size = 121

    eps_r = np.ones((size, size))
    sigma = np.zeros((size, size))
    iy0, ix0 = size // 2, size // 2

    E_direct = solve_field(eps_r, sigma, freq_hz, dx, iy0, ix0)
    E_multi, info = solve_field_multires(eps_r, sigma, freq_hz, dx, iy0, ix0)

    rel_error = np.linalg.norm(E_multi - E_direct) / np.linalg.norm(E_direct)
    print(f"\n[multires free-space] info={info} rel_error={rel_error:.3e}")

    assert info["n_tiles"] > 1
    assert rel_error < 1e-8


def test_multires_matches_single_resolution_with_wall():
    freq_hz = 2.4e9
    dx = (C0 / freq_hz) / 15
    size = 121
    width = height = (size - 1) * dx

    source = Source(x=width * 0.3, y=height * 0.5)
    scene = Scene(
        width=width,
        height=height,
        walls=[Wall(width * 0.5, 0.0, width * 0.5, height, material="concrete", thickness=0.15)],
        sources=[source],
    )
    grid = build_grid(scene, dx)
    iy0, ix0 = grid.xy_to_index(source.x, source.y)

    E_direct = solve_field(grid.eps_r, grid.sigma, freq_hz, dx, iy0, ix0)
    E_multi, info = solve_field_multires(grid.eps_r, grid.sigma, freq_hz, dx, iy0, ix0)

    rel_error = np.linalg.norm(E_multi - E_direct) / np.linalg.norm(E_direct)
    print(f"\n[multires with wall] info={info} rel_error={rel_error:.3e}")

    assert rel_error < 1e-8


def test_multires_timing_on_larger_grid():
    """Not a correctness assertion -- reports whether tiled substructuring
    is competitive with a single full-grid direct solve at a larger size,
    where its parallelizable small-factorization structure should start to
    pay off relative to one big sparse LU."""
    freq_hz = 2.4e9
    dx = (C0 / freq_hz) / 15
    size = 241

    eps_r = np.ones((size, size))
    sigma = np.zeros((size, size))
    iy0, ix0 = size // 2, size // 2

    t0 = time.perf_counter()
    E_direct = solve_field(eps_r, sigma, freq_hz, dx, iy0, ix0)
    t_direct = time.perf_counter() - t0

    t0 = time.perf_counter()
    E_multi, info = solve_field_multires(eps_r, sigma, freq_hz, dx, iy0, ix0, tile_size=24)
    t_multi = time.perf_counter() - t0

    rel_error = np.linalg.norm(E_multi - E_direct) / np.linalg.norm(E_direct)
    print(
        f"\n[multires timing, size={size}] info={info} rel_error={rel_error:.3e} "
        f"t_direct={t_direct:.3f}s t_multi={t_multi:.3f}s"
    )

    assert rel_error < 1e-6
