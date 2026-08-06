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
