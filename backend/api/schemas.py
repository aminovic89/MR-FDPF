from typing import Literal

from pydantic import BaseModel, Field


class WallIn(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float
    material: str = "concrete"
    thickness: float = 0.15


class SourceIn(BaseModel):
    x: float
    y: float
    power_dbm: float = 20.0


class SimulateRequest(BaseModel):
    width: float
    height: float
    walls: list[WallIn] = Field(default_factory=list)
    sources: list[SourceIn]
    freq_mhz: float = 2400.0
    points_per_wavelength: int = 15
    mode: Literal["single", "multi"] = "single"


class SimulateResponse(BaseModel):
    nx: int
    ny: int
    dx: float
    power_dbm: list[list[float]]
    elapsed_s: float
    mode: str


class MaterialOut(BaseModel):
    name: str
    eps_r: float
    sigma: float
