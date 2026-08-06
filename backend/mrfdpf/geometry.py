"""Scene description: domain, walls and sources.

Coordinates are in meters, with the origin at the domain's bottom-left
corner (x to the right, y upward). This is the shared representation used
by the grid rasterizer, the solvers and the JSON API.
"""

from dataclasses import dataclass, field


@dataclass
class Wall:
    x1: float
    y1: float
    x2: float
    y2: float
    material: str = "concrete"
    thickness: float = 0.15  # meters


@dataclass
class Source:
    x: float
    y: float
    power_dbm: float = 20.0  # EIRP


@dataclass
class Scene:
    width: float  # meters
    height: float  # meters
    walls: list[Wall] = field(default_factory=list)
    sources: list[Source] = field(default_factory=list)


@dataclass
class Floor:
    """One story of a building: its own 2D layout (walls + sources), sharing
    the building's footprint (width/height)."""

    walls: list[Wall] = field(default_factory=list)
    sources: list[Source] = field(default_factory=list)


@dataclass
class Building:
    """A stack of floors sharing one footprint. Vertical (cross-floor)
    coupling is modeled as a flat per-floor-slab attenuation rather than a
    true 3D solve -- see solver.run_building_simulation for the physical
    reasoning and its limits."""

    width: float
    height: float
    floors: list[Floor] = field(default_factory=list)
    floor_attenuation_db: float = 15.0
