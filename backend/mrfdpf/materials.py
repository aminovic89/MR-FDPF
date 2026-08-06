"""Material presets for wall segments.

Each material is defined by its relative permittivity ``eps_r`` and
conductivity ``sigma`` (S/m), the standard pair used to build a lossy
dielectric complex permittivity ``eps_r - j*sigma/(omega*eps0)``.

Values are typical figures at ~2.4-5 GHz gathered from common indoor
propagation modeling references (ITU-R P.2040 and similar). They are
approximations meant to give qualitatively correct reflection/attenuation
behaviour, not metrology-grade figures.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Material:
    name: str
    eps_r: float
    sigma: float  # S/m


MATERIALS: dict[str, Material] = {
    "air": Material("air", 1.0, 0.0),
    "concrete": Material("concrete", 5.31, 0.0326),
    "brick": Material("brick", 3.75, 0.038),
    "drywall": Material("drywall", 2.94, 0.0116),
    "glass": Material("glass", 6.27, 0.0043),
    "wood": Material("wood", 1.99, 0.0047),
    "metal": Material("metal", 1.0, 1.0e7),
}


def get_material(name: str) -> Material:
    try:
        return MATERIALS[name]
    except KeyError as exc:
        raise ValueError(
            f"Unknown material '{name}'. Available: {sorted(MATERIALS)}"
        ) from exc
