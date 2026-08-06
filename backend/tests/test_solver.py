import numpy as np

from mrfdpf.geometry import Scene, Source, Wall
from mrfdpf.solver import run_simulation


def test_run_simulation_free_space():
    scene = Scene(width=1.0, height=1.0, sources=[Source(x=0.5, y=0.5, power_dbm=20.0)])
    result = run_simulation(scene, freq_hz=2.4e9, points_per_wavelength=15, mode="single")

    assert result.power_dbm.shape == result.grid_shape
    iy, ix = result.grid_shape[0] // 2, result.grid_shape[1] // 2
    # power should decrease monotonically away from the source along one axis
    center_power = result.power_dbm[iy, ix]
    far_power = result.power_dbm[iy, ix + 20]
    assert center_power > far_power


def test_run_simulation_requires_source():
    scene = Scene(width=1.0, height=1.0, sources=[])
    try:
        run_simulation(scene, freq_hz=2.4e9)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_run_simulation_multi_matches_single():
    scene = Scene(
        width=1.0,
        height=1.0,
        walls=[Wall(0.5, 0.0, 0.5, 1.0, material="concrete", thickness=0.1)],
        sources=[Source(x=0.3, y=0.5, power_dbm=20.0)],
    )
    result_single = run_simulation(scene, freq_hz=2.4e9, mode="single")
    result_multi = run_simulation(scene, freq_hz=2.4e9, mode="multi")

    diff = np.abs(result_single.power_dbm - result_multi.power_dbm)
    assert np.max(diff) < 1e-4
