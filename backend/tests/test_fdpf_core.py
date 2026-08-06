"""Validate the single-resolution solver against the analytical 2D free-space
Green's function of the Helmholtz equation.

Under the exp(+j*omega*t) convention used by fdpf_core, a point source in an
unbounded medium radiates a field proportional to hankel2(0, k0*r). We solve
on a finite grid with Mur absorbing boundaries (no walls), sample the field
at points away from the source singularity and away from the boundary, and
fit a single complex scale factor to the analytical Hankel profile. A small
residual after that fit confirms the discretization (wavenumber, radial
decay, phase velocity) is correct; it does not depend on getting the
absolute source-normalization constant exactly right.
"""

import numpy as np
from scipy.special import hankel2

from mrfdpf.fdpf_core import solve_field, C0


def _sample_offsets(max_r_cells, min_r_cells):
    offsets = []
    for diy in range(-max_r_cells, max_r_cells + 1, 4):
        for dix in range(-max_r_cells, max_r_cells + 1, 4):
            r_cells = np.hypot(diy, dix)
            if min_r_cells <= r_cells <= max_r_cells:
                offsets.append((diy, dix))
    return offsets


def test_free_space_matches_hankel2():
    freq_hz = 2.4e9
    wavelength = C0 / freq_hz
    dx = wavelength / 15

    domain = 1.0  # meters
    eps_r = np.ones((121, 121))
    sigma = np.zeros((121, 121))
    ny, nx = eps_r.shape
    iy0, ix0 = ny // 2, nx // 2

    E = solve_field(eps_r, sigma, freq_hz, dx, iy0, ix0)

    k0 = 2 * np.pi * freq_hz / C0
    offsets = _sample_offsets(max_r_cells=40, min_r_cells=10)
    assert len(offsets) > 20

    sim_vals = np.array([E[iy0 + diy, ix0 + dix] for diy, dix in offsets])
    r = np.array([np.hypot(diy, dix) for diy, dix in offsets]) * dx
    ref_vals = hankel2(0, k0 * r)

    # least-squares complex scale fit: minimize ||sim - C * ref||
    C = np.vdot(ref_vals, sim_vals) / np.vdot(ref_vals, ref_vals)
    residual = sim_vals - C * ref_vals
    rel_error = np.linalg.norm(residual) / np.linalg.norm(sim_vals)

    assert rel_error < 0.05, f"relative error too high: {rel_error:.4f}"


def test_field_decays_with_distance():
    freq_hz = 2.4e9
    wavelength = C0 / freq_hz
    dx = wavelength / 15
    eps_r = np.ones((121, 121))
    sigma = np.zeros((121, 121))
    ny, nx = eps_r.shape
    iy0, ix0 = ny // 2, nx // 2

    E = solve_field(eps_r, sigma, freq_hz, dx, iy0, ix0)
    mag = np.abs(E)

    near = mag[iy0, ix0 + 10]
    mid = mag[iy0, ix0 + 25]
    far = mag[iy0, ix0 + 40]

    assert near > mid > far
