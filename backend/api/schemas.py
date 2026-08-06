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


class FloorIn(BaseModel):
    walls: list[WallIn] = Field(default_factory=list)
    sources: list[SourceIn] = Field(default_factory=list)


class SimulateBuildingRequest(BaseModel):
    width: float
    height: float
    floors: list[FloorIn]
    floor_attenuation_db: float = 15.0
    freq_mhz: float = 2400.0
    points_per_wavelength: int = 15
    mode: Literal["single", "multi"] = "single"


class SimulateBuildingResponse(BaseModel):
    nx: int
    ny: int
    dx: float
    floors_power_dbm: list[list[list[float]]]
    elapsed_s: float
    mode: str


class JobStartResponse(BaseModel):
    job_id: str


class JobStatusResponse(BaseModel):
    status: Literal["pending", "running", "done", "error"]
    progress: float
    message: str
    result: SimulateBuildingResponse | None = None
    error: str | None = None
