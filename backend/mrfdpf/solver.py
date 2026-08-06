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
from typing import Callable

import numpy as np

from .fdpf_core import C0, solve_field
from .geometry import Building, Scene
from .grid import Grid, build_grid
from .multires import solve_field_multires


@dataclass
class SimulationResult:
    power_dbm: np.ndarray
    grid_shape: tuple[int, int]
    dx: float
    elapsed_s: float
    mode: str


@dataclass
class BuildingSimulationResult:
    floors_power_dbm: list[np.ndarray]
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


def run_building_simulation(
    building: Building,
    freq_hz: float,
    points_per_wavelength: int = 15,
    mode: str = "single",
    progress_callback: Callable[[float, str], None] | None = None,
) -> BuildingSimulationResult:
    """Multi-floor coverage. Each floor is solved as its own independent 2D
    problem against its own walls -- this is a genuine 2D FDPF solve per
    floor, not a shortcut. Cross-floor coupling is *not* a 3D solve (that
    would need real 3D meshing/materials and is a much larger project);
    instead a source's contribution to a floor other than its own reuses
    that source's own-floor field pattern (so shadowing/interference from
    its own floor's walls is preserved) and adds a flat
    ``floor_attenuation_db`` penalty per floor slab crossed. This is the
    same simplification used by practical indoor-coverage tools (an
    ITU-R P.1238-style floor penetration factor) -- it does not model
    diffraction specific to the *receiving* floor's own layout for that
    cross-floor contribution, only for same-floor contributions.
    """
    if not building.floors:
        raise ValueError("building has no floors")
    if not any(floor.sources for floor in building.floors):
        raise ValueError("building has no sources")
    if mode not in ("single", "multi"):
        raise ValueError(f"unknown mode '{mode}', expected 'single' or 'multi'")

    dx = _dx_for_resolution(freq_hz, points_per_wavelength)
    grids = [
        build_grid(Scene(building.width, building.height, walls=floor.walls), dx)
        for floor in building.floors
    ]
    ny, nx = grids[0].eps_r.shape
    n_floors = len(building.floors)
    power_linear_mw = [np.zeros((ny, nx)) for _ in range(n_floors)]

    total_sources = sum(len(floor.sources) for floor in building.floors)
    completed = 0
    if progress_callback:
        progress_callback(0.0, f"grille {ny}x{nx} construite, 0/{total_sources} sources résolues")

    t0 = time.perf_counter()
    for source_floor, floor in enumerate(building.floors):
        grid = grids[source_floor]
        for source in floor.sources:
            iy0, ix0 = grid.xy_to_index(source.x, source.y)
            rel_dbm = _source_power_dbm(grid, grid.eps_r, grid.sigma, freq_hz, dx, iy0, ix0, mode)
            for k in range(n_floors):
                floor_loss = building.floor_attenuation_db * abs(k - source_floor)
                power_dbm = source.power_dbm + rel_dbm - floor_loss
                power_linear_mw[k] += 10 ** (power_dbm / 10.0)
            completed += 1
            if progress_callback:
                progress_callback(completed / total_sources, f"{completed}/{total_sources} sources résolues")
    elapsed = time.perf_counter() - t0

    floors_power_dbm = []
    for power_mw in power_linear_mw:
        with np.errstate(divide="ignore"):
            floors_power_dbm.append(10 * np.log10(np.maximum(power_mw, 1e-300)))

    return BuildingSimulationResult(
        floors_power_dbm=floors_power_dbm,
        grid_shape=(ny, nx),
        dx=dx,
        elapsed_s=elapsed,
        mode=mode,
    )
