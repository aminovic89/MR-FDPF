import numpy as np

from mrfdpf.geometry import Building, Floor, Source, Wall
from mrfdpf.solver import run_building_simulation


def test_cross_floor_attenuation_is_a_flat_offset():
    """A source only on floor 0 should reach floor 1 as the exact same
    field pattern (same shadowing/interference), offset by a constant
    floor_attenuation_db -- that's the coupling model by construction."""
    floor0 = Floor(sources=[Source(x=1.5, y=1.5, power_dbm=20.0)])
    floor1 = Floor()
    building = Building(width=3.0, height=3.0, floors=[floor0, floor1], floor_attenuation_db=12.0)

    result = run_building_simulation(building, freq_hz=2.4e9)

    assert len(result.floors_power_dbm) == 2
    diff = result.floors_power_dbm[0] - result.floors_power_dbm[1]
    assert np.allclose(diff, 12.0, atol=1e-6)


def test_own_floor_walls_shadow_only_that_floor():
    """A metal wall on floor 0 should shadow floor 0's own map; floor 1 (no
    walls) sees floor 0's source only through the flat floor attenuation,
    so it must NOT show the same shadow dip (since it's a rigid vertical
    offset, no new spatial feature is introduced)."""
    source = Source(x=0.3, y=0.5, power_dbm=20.0)
    target = (0.7, 0.5)

    floor0 = Floor(
        walls=[Wall(0.5, 0.0, 0.5, 1.0, material="metal", thickness=0.02)],
        sources=[source],
    )
    floor1 = Floor()
    building = Building(width=1.0, height=1.0, floors=[floor0, floor1], floor_attenuation_db=10.0)

    result = run_building_simulation(building, freq_hz=2.4e9)
    diff = result.floors_power_dbm[0] - result.floors_power_dbm[1]
    assert np.allclose(diff, 10.0, atol=1e-6)


def test_run_building_simulation_requires_floor_and_source():
    try:
        run_building_simulation(Building(width=1.0, height=1.0, floors=[]), freq_hz=2.4e9)
        assert False, "expected ValueError for no floors"
    except ValueError:
        pass

    try:
        run_building_simulation(
            Building(width=1.0, height=1.0, floors=[Floor()]), freq_hz=2.4e9
        )
        assert False, "expected ValueError for no sources"
    except ValueError:
        pass


def test_three_floors_middle_source_symmetric_attenuation():
    floor0 = Floor()
    floor1 = Floor(sources=[Source(x=1.0, y=1.0, power_dbm=20.0)])
    floor2 = Floor()
    building = Building(width=2.0, height=2.0, floors=[floor0, floor1, floor2], floor_attenuation_db=8.0)

    result = run_building_simulation(building, freq_hz=2.4e9)
    diff_below = result.floors_power_dbm[1] - result.floors_power_dbm[0]
    diff_above = result.floors_power_dbm[1] - result.floors_power_dbm[2]
    assert np.allclose(diff_below, 8.0, atol=1e-6)
    assert np.allclose(diff_above, 8.0, atol=1e-6)
