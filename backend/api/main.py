from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from mrfdpf.geometry import Scene, Source, Wall
from mrfdpf.materials import MATERIALS
from mrfdpf.solver import run_simulation

from .schemas import MaterialOut, SimulateRequest, SimulateResponse

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

app = FastAPI(title="MR-FDPF Indoor Propagation Simulator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


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


if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/")
    def index():
        return FileResponse(FRONTEND_DIR / "index.html")
