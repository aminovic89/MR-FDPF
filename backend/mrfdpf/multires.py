"""Multi-resolution (MR-FDPF-style) hierarchical acceleration.

Honest note on the algorithmic choice (two approaches were tried and
rejected before this one -- see git history / PR description if you want
the detail): the discrete Helmholtz operator is indefinite, not
diagonally dominant the way a Poisson operator is. That makes it a known
hard case for the usual "cheap acceleration" tools:

* Classical geometric multigrid (Galerkin coarsening + weighted-Jacobi
  smoothing) diverged in testing -- point-relaxation smoothers are well
  documented in the numerical PDE literature to be unstable for
  indefinite Helmholtz operators.
* Overlapping Schwarz domain decomposition with plain Dirichlet
  transmission between subdomains also diverged on more sweeps -- this
  matches the classical result that Dirichlet-Dirichlet Schwarz for the
  Helmholtz equation is not convergent in general; that's exactly why the
  "optimized Schwarz method" literature uses Robin/impedance transmission
  conditions instead.

What this module implements instead is **exact substructuring** (static
condensation / one-level Schur-complement domain decomposition, the same
idea nested-dissection sparse direct solvers use internally):

1. The fine grid is partitioned into non-overlapping tiles separated by
   single-cell-wide separator rows/columns. With a 5-point stencil, a
   1-cell separator fully decouples one tile's interior from another's,
   so the interior/interior block of the reordered operator is exactly
   block-diagonal (one small block per tile).
2. Each tile's block is factorized independently (this is the
   "per-resolution-cell" work, and is trivially parallelizable across
   tiles).
3. Those factorizations are used to eliminate all interior unknowns,
   producing a Schur complement system over only the separator ("coarse
   interface") unknowns -- a much smaller dense system, solved directly.
4. Back-substitution recovers each tile's interior values from the
   interface solution, again independently per tile.

This is algebraically *exact* (up to floating point), so there is no
divergence risk of any kind, and it validates against fdpf_core's direct
solve to near machine precision in test_multires.py. The trade-off vs a
"true" coarse-resolution multi-resolution method is that this doesn't
skip fine-grid physics anywhere -- the speed benefit instead comes from
replacing one large factorization with many small, parallelizable ones
plus one small interface solve, which is where the actual gain over a
naive full-grid direct solve shows up as problems get larger.
"""

from __future__ import annotations

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from .fdpf_core import build_operator


def _separator_masks(ny: int, nx: int, tile_size: int):
    is_sep_row = np.zeros(ny, dtype=bool)
    r = tile_size
    while r < ny:
        is_sep_row[r] = True
        r += tile_size + 1

    is_sep_col = np.zeros(nx, dtype=bool)
    c = tile_size
    while c < nx:
        is_sep_col[c] = True
        c += tile_size + 1

    return is_sep_row, is_sep_col


def _build_permutation(ny: int, nx: int, tile_size: int):
    """Reorder grid cells as [tile_1 interior, tile_2 interior, ..., separator].
    Returns (perm, n_interior, tile_slices) where tile_slices[k] = (start, end)
    gives tile k's range within the interior block of the permuted ordering."""
    is_sep_row, is_sep_col = _separator_masks(ny, nx, tile_size)
    IY, IX = np.meshgrid(np.arange(ny), np.arange(nx), indexing="ij")
    idx = IY * nx + IX
    sep_mask = is_sep_row[:, None] | is_sep_col[None, :]

    prefix_row = np.concatenate([[0], np.cumsum(is_sep_row.astype(int))])[:-1]
    prefix_col = np.concatenate([[0], np.cumsum(is_sep_col.astype(int))])[:-1]
    n_tile_cols = int(prefix_col.max()) + 1
    tile_id = prefix_row[IY] * n_tile_cols + prefix_col[IX]

    interior_mask = ~sep_mask
    idx_interior = idx[interior_mask]
    idx_separator = idx[sep_mask]
    tile_ids = tile_id[interior_mask]

    order = np.argsort(tile_ids, kind="stable")
    idx_interior_sorted = idx_interior[order]
    tile_ids_sorted = tile_ids[order]

    unique_tiles, tile_starts = np.unique(tile_ids_sorted, return_index=True)
    tile_starts = list(tile_starts) + [len(tile_ids_sorted)]
    tile_slices = [(tile_starts[i], tile_starts[i + 1]) for i in range(len(unique_tiles))]

    perm = np.concatenate([idx_interior_sorted, idx_separator])
    n_interior = len(idx_interior_sorted)
    return perm, n_interior, tile_slices


def solve_field_multires(
    eps_r: np.ndarray,
    sigma: np.ndarray,
    freq_hz: float,
    dx: float,
    source_iy: int,
    source_ix: int,
    amplitude: complex = 1.0,
    tile_size: int = 20,
):
    """Exact substructured solve. Returns (E, info) where info reports the
    tile layout for diagnostics/benchmarking."""
    ny, nx = eps_r.shape
    n = ny * nx

    A, _ = build_operator(eps_r, sigma, freq_hz, dx)
    b = np.zeros(n, dtype=np.complex128)
    b[source_iy * nx + source_ix] = -amplitude / dx**2

    perm, n_interior, tile_slices = _build_permutation(ny, nx, tile_size)
    n_sep = n - n_interior

    A_perm = A[perm, :][:, perm].tocsr()
    b_perm = b[perm]

    A_II = A_perm[:n_interior, :n_interior].tocsr()
    A_IS = A_perm[:n_interior, n_interior:].tocsr()
    A_SI = A_perm[n_interior:, :n_interior].tocsr()
    S = A_perm[n_interior:, n_interior:].toarray()
    b_I = b_perm[:n_interior]
    rhs_adj = b_perm[n_interior:].copy()

    tile_Y = []
    tile_zI = []
    for start, end in tile_slices:
        block = A_II[start:end, start:end].tocsc()
        lu = spla.splu(block)

        ais_block = A_IS[start:end, :]
        y = lu.solve(ais_block.toarray()) if ais_block.nnz > 0 else np.zeros(
            (end - start, n_sep), dtype=np.complex128
        )
        z = lu.solve(b_I[start:end])

        asi_block = A_SI[:, start:end]
        S -= asi_block @ y
        rhs_adj -= asi_block @ z

        tile_Y.append(y)
        tile_zI.append(z)

    x_S = np.linalg.solve(S, rhs_adj)

    x_I = np.zeros(n_interior, dtype=np.complex128)
    for (start, end), y, z in zip(tile_slices, tile_Y, tile_zI):
        x_I[start:end] = z - y @ x_S

    x_perm = np.concatenate([x_I, x_S])
    x = np.zeros(n, dtype=np.complex128)
    x[perm] = x_perm

    info = {"n_tiles": len(tile_slices), "n_interior": n_interior, "n_separator": n_sep}
    return x.reshape(ny, nx), info
