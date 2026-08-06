"""Single-resolution FDPF core solver.

Solves the 2D scalar Helmholtz equation

    (d2/dx2 + d2/dy2 + k(x, y)^2) E = source

on a uniform grid via a direct sparse solve of the 5-point finite-difference
system, with 1st-order Mur absorbing boundary conditions on all four domain
edges (so a bounded compute box behaves like an open domain).

Time convention: exp(+j*omega*t). Under this convention an outgoing
cylindrical wave in free space is proportional to
``scipy.special.hankel2(0, k0 * r)`` — that identity is what the analytical
validation test in ``test_fdpf_core.py`` checks against.

This solver is the "ground truth" single-resolution reference against which
the multi-resolution solver (multires.py) is validated.
"""

from __future__ import annotations

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

C0 = 299_792_458.0
EPS0 = 8.8541878128e-12


def build_operator(
    eps_r: np.ndarray, sigma: np.ndarray, freq_hz: float, dx: float
) -> tuple[sp.csr_matrix, float]:
    """Assemble the sparse complex operator A such that A @ E.ravel() equals
    the discretized (Helmholtz + Mur ABC) left-hand side."""
    ny, nx = eps_r.shape
    omega = 2 * np.pi * freq_hz
    k0 = omega / C0
    eps_complex = eps_r - 1j * sigma / (omega * EPS0)
    k2 = (k0**2) * eps_complex

    inv_dx2 = 1.0 / dx**2
    idx = np.arange(ny * nx).reshape(ny, nx)

    rows_list = []
    cols_list = []
    data_list = []

    def add_edges(rows, cols, value):
        rows_list.append(rows.ravel())
        cols_list.append(cols.ravel())
        data_list.append(np.full(rows.size, value, dtype=np.complex128))

    # interior couplings (each pair added both ways -> symmetric Laplacian)
    add_edges(idx[:, :-1], idx[:, 1:], inv_dx2)
    add_edges(idx[:, 1:], idx[:, :-1], inv_dx2)
    add_edges(idx[:-1, :], idx[1:, :], inv_dx2)
    add_edges(idx[1:, :], idx[:-1, :], inv_dx2)

    diag = -4 * inv_dx2 + k2

    # Mur 1st-order ABC: a missing neighbor is eliminated in favor of the
    # opposite (inward) neighbor, whose coefficient doubles, plus a
    # -2j*k0/dx correction on the diagonal. See module docstring for the
    # sign convention.
    abc_term = -2j * k0 / dx

    add_edges(idx[:, 0], idx[:, 1], inv_dx2)  # left boundary
    diag[:, 0] += abc_term
    add_edges(idx[:, -1], idx[:, -2], inv_dx2)  # right boundary
    diag[:, -1] += abc_term
    add_edges(idx[0, :], idx[1, :], inv_dx2)  # top boundary
    diag[0, :] += abc_term
    add_edges(idx[-1, :], idx[-2, :], inv_dx2)  # bottom boundary
    diag[-1, :] += abc_term

    rows_list.append(idx.ravel())
    cols_list.append(idx.ravel())
    data_list.append(diag.ravel().astype(np.complex128))

    rows = np.concatenate(rows_list)
    cols = np.concatenate(cols_list)
    data = np.concatenate(data_list)

    n = nx * ny
    A = sp.coo_matrix((data, (rows, cols)), shape=(n, n)).tocsr()
    return A, k0


def solve_field(
    eps_r: np.ndarray,
    sigma: np.ndarray,
    freq_hz: float,
    dx: float,
    source_iy: int,
    source_ix: int,
    amplitude: complex = 1.0,
    use_direct: bool = True,
) -> np.ndarray:
    """Solve for the complex field E given a point source at (source_iy,
    source_ix). Returns E with shape (ny, nx).

    ``use_direct`` defaults to True (sparse LU via spsolve) and should be
    left there: the discrete Helmholtz operator is indefinite, and plain
    unpreconditioned GMRES on it is not reliably convergent (the same
    "Helmholtz is not diagonally dominant" issue documented at length in
    multires.py bit us here too during development -- a naive GMRES
    fallback for large grids stalled instead of erroring out cleanly).
    Setting use_direct=False is only for callers that supply their own
    validated preconditioner; there isn't a safe default iterative path
    here yet.
    """
    ny, nx = eps_r.shape
    A, _ = build_operator(eps_r, sigma, freq_hz, dx)

    n = nx * ny
    b = np.zeros(n, dtype=np.complex128)
    # Discrete Dirac delta of unit integral over one cell has value 1/dx^2;
    # the minus sign matches (grad^2 + k^2) G = -delta for the source term.
    b[source_iy * nx + source_ix] = -amplitude / dx**2

    if use_direct:
        E = spla.spsolve(A.tocsc(), b)
    else:
        E, info = spla.gmres(A, b, atol=1e-8, rtol=1e-8, maxiter=200)
        if info != 0:
            raise RuntimeError(f"GMRES did not converge (info={info})")

    return E.reshape(ny, nx)
