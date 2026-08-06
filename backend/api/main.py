from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from mrfdpf.geometry import Building, Floor, Scene, Source, Wall
from mrfdpf.materials import MATERIALS
from mrfdpf.solver import BuildingSimulationResult, run_building_simulation, run_simulation

from . import jobs
from .schemas import (
    JobStartResponse,
    JobStatusResponse,
    MaterialOut,
    SimulateBuildingRequest,
    SimulateBuildingResponse,
    SimulateRequest,
    SimulateResponse,
)

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

app = FastAPI(title="MR-FDPF Indoor Propagation Simulator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def no_cache_static(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static") or request.url.path == "/":
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/api/materials", response_model=list[MaterialOut])
def list_materials():
    return [MaterialOut(name=m.name, eps_r=m.eps_r, sigma=m.sigma) for m in MATERIALS.values()]


@app.post("/api/simulate", response_model=SimulateResponse)
def simulate(req: SimulateRequest):
    if not req.sources:
        raise HTTPException(400, "at least one source is required")
    for wall in req.walls:
        if wall.material not in MATERIALS:
            raise HTTPException(400, f"unknown material '{wall.material}'")

    scene = Scene(
        width=req.width,
        height=req.height,
        walls=[Wall(w.x1, w.y1, w.x2, w.y2, w.material, w.thickness) for w in req.walls],
        sources=[Source(s.x, s.y, s.power_dbm) for s in req.sources],
    )

    try:
        result = run_simulation(
            scene,
            freq_hz=req.freq_mhz * 1e6,
            points_per_wavelength=req.points_per_wavelength,
            mode=req.mode,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    return SimulateResponse(
        nx=result.grid_shape[1],
        ny=result.grid_shape[0],
        dx=result.dx,
        power_dbm=result.power_dbm.tolist(),
        elapsed_s=result.elapsed_s,
        mode=result.mode,
    )


def _build_building(req: SimulateBuildingRequest) -> Building:
    if not req.floors:
        raise HTTPException(400, "at least one floor is required")
    if not any(f.sources for f in req.floors):
        raise HTTPException(400, "at least one source is required")
    for floor in req.floors:
        for wall in floor.walls:
            if wall.material not in MATERIALS:
                raise HTTPException(400, f"unknown material '{wall.material}'")

    return Building(
        width=req.width,
        height=req.height,
        floor_attenuation_db=req.floor_attenuation_db,
        floors=[
            Floor(
                walls=[Wall(w.x1, w.y1, w.x2, w.y2, w.material, w.thickness) for w in f.walls],
                sources=[Source(s.x, s.y, s.power_dbm) for s in f.sources],
            )
            for f in req.floors
        ],
    )


def _building_result_to_response(result: BuildingSimulationResult) -> SimulateBuildingResponse:
    return SimulateBuildingResponse(
        nx=result.grid_shape[1],
        ny=result.grid_shape[0],
        dx=result.dx,
        floors_power_dbm=[p.tolist() for p in result.floors_power_dbm],
        elapsed_s=result.elapsed_s,
        mode=result.mode,
    )


@app.post("/api/simulate_building", response_model=SimulateBuildingResponse)
def simulate_building(req: SimulateBuildingRequest):
    building = _build_building(req)
    try:
        result = run_building_simulation(
            building,
            freq_hz=req.freq_mhz * 1e6,
            points_per_wavelength=req.points_per_wavelength,
            mode=req.mode,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    return _building_result_to_response(result)


@app.post("/api/simulate_building/start", response_model=JobStartResponse)
def start_simulate_building(req: SimulateBuildingRequest):
    """Same simulation as /api/simulate_building, but run in a background
    thread and polled via /api/jobs/{id} -- for a fine-resolution scene the
    synchronous endpoint can take tens of seconds, during which a plain
    blocking call would leave the UI with no feedback at all."""
    building = _build_building(req)
    job = jobs.create_job()
    jobs.run_in_background(
        job,
        run_building_simulation,
        building,
        freq_hz=req.freq_mhz * 1e6,
        points_per_wavelength=req.points_per_wavelength,
        mode=req.mode,
    )
    return JobStartResponse(job_id=job.id)


@app.get("/api/jobs/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str):
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(404, "job not found")

    result = None
    if job.status == "done":
        result = _building_result_to_response(job.result)

    return JobStatusResponse(
        status=job.status,
        progress=job.progress,
        message=job.message,
        result=result,
        error=job.error,
    )


if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/")
    def index():
        return FileResponse(FRONTEND_DIR / "index.html")
