"""Unified solver facade used by the API layer.

Builds a grid from a Scene at a resolution derived from the wavelength,
runs the requested backend (single-resolution direct solve, or the
multi-resolution exact substructuring solve), and converts the resulting
complex field(s) into a received-power coverage map in dBm.

Calibration note: the underlying PDE solve is done with a unit-amplitude
point source in solver-internal units, not an absolute physical field
strength. To turn |E|^2 into a received power in dBm we anchor the path
loss to 0 dB at one grid cell away from the transmitter (the closest point
where the discretization is not singular) and add the transmitter's power
budget on top. This makes every *spatial variation* in the resulting map
(shadowing, multipath interference, distance decay) directly physical --
it comes straight out of solving the wave equation -- while the absolute
level is a simplification appropriate for a coverage-visualization tool,
not a metrology instrument.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np

from .fdpf_core import C0, solve_field
from .geometry import Scene
from .grid import Grid, build_grid
from .multires import solve_field_multires


@dataclass
class SimulationResult:
    power_dbm: np.ndarray
    grid_shape: tuple[int, int]
    dx: float
    elapsed_s: float
    mode: str


def _dx_for_resolution(freq_hz: float, points_per_wavelength: int) -> float:
    wavelength = C0 / freq_hz
    return wavelength / points_per_wavelength


def _source_power_dbm(grid: Grid, eps_r, sigma, freq_hz, dx, iy0, ix0, mode: str) -> np.ndarray:
    if mode == "multi":
        E, _info = solve_field_multires(eps_r, sigma, freq_hz, dx, iy0, ix0)
    else:
        E = solve_field(eps_r, sigma, freq_hz, dx, iy0, ix0)

    mag2 = np.abs(E) ** 2
    ny, nx = mag2.shape
    ref_ix = min(ix0 + 1, nx - 1)
    ref_val = mag2[iy0, ref_ix]
    if ref_val <= 0:
        ref_val = np.max(mag2[mag2 > 0]) if np.any(mag2 > 0) else 1.0

    with np.errstate(divide="ignore"):
        return 10 * np.log10(np.maximum(mag2 / ref_val, 1e-300))


def run_simulation(
    scene: Scene,
    freq_hz: float,
    points_per_wavelength: int = 15,
    mode: str = "single",
) -> SimulationResult:
    if not scene.sources:
        raise ValueError("scene has no sources")
    if mode not in ("single", "multi"):
        raise ValueError(f"unknown mode '{mode}', expected 'single' or 'multi'")

    dx = _dx_for_resolution(freq_hz, points_per_wavelength)
    grid = build_grid(scene, dx)
    ny, nx = grid.eps_r.shape

    t0 = time.perf_counter()
    power_linear_mw = np.zeros((ny, nx))
    for source in scene.sources:
        iy0, ix0 = grid.xy_to_index(source.x, source.y)
        rel_dbm = _source_power_dbm(grid, grid.eps_r, grid.sigma, freq_hz, dx, iy0, ix0, mode)
        power_dbm = source.power_dbm + rel_dbm
        power_linear_mw += 10 ** (power_dbm / 10.0)
    elapsed = time.perf_counter() - t0

    with np.errstate(divide="ignore"):
        total_power_dbm = 10 * np.log10(np.maximum(power_linear_mw, 1e-300))

    return SimulationResult(
        power_dbm=total_power_dbm,
        grid_shape=(ny, nx),
        dx=dx,
        elapsed_s=elapsed,
        mode=mode,
    )
