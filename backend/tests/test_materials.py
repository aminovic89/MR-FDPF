from mrfdpf.materials import MATERIALS, get_material


def test_get_material_known():
    concrete = get_material("concrete")
    assert concrete.eps_r > 1.0
    assert concrete.sigma > 0.0


def test_get_material_unknown_raises():
    try:
        get_material("unobtainium")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_metal_is_near_perfect_conductor():
    metal = MATERIALS["metal"]
    assert metal.sigma > 1e6
