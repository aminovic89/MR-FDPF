import { renderHeatmapToCanvas } from "./heatmap-render.js?v=7";

const MATERIAL_COLORS = {
  concrete: "#8a8a8a",
  brick: "#b5651d",
  drywall: "#d8c9a3",
  glass: "#7ec8e3",
  wood: "#a0703a",
  metal: "#c7c9d1",
};

const MAX_CANVAS_DIM = 700;
const DOOR_WIDTH = 0.9; // meters, standard door opening

function emptyFloor() {
  return { walls: [], sources: [] };
}

export class CanvasEditor {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.building = { width: 8, height: 6, floorAttenuationDb: 15, floors: [emptyFloor()] };
    this.currentFloor = 0;
    this.tool = "wall";
    this.material = "concrete";
    this.sourcePower = 20;
    this.lastFloorsResult = null; // array of 2D power_dbm grids, one per floor
    this.lastRange = null;
    this.lastGridInfo = null; // { dx, nx, ny }
    this.inspectPoint = null; // { xm, ym, value }
    this.onInspect = null; // callback(value, xm, ym)
    this.dragStart = null;

    this.scale = this._computeScale();
    this._resizeCanvas();

    canvas.addEventListener("mousedown", (e) => this._onMouseDown(e));
    canvas.addEventListener("mousemove", (e) => this._onMouseMove(e));
    canvas.addEventListener("mouseup", (e) => this._onMouseUp(e));
    canvas.addEventListener("mouseleave", () => {
      this.dragStart = null;
      this.render();
    });

    this.render();
  }

  get floor() {
    return this.building.floors[this.currentFloor];
  }

  get floorCount() {
    return this.building.floors.length;
  }

  _computeScale() {
    const scale = MAX_CANVAS_DIM / Math.max(this.building.width, this.building.height);
    return Math.max(15, Math.min(120, scale));
  }

  _resizeCanvas() {
    this.canvas.width = Math.round(this.building.width * this.scale);
    this.canvas.height = Math.round(this.building.height * this.scale);
  }

  setDomain(width, height) {
    this.building.width = width;
    this.building.height = height;
    this.scale = this._computeScale();
    this._resizeCanvas();
    this.lastFloorsResult = null;
    this.render();
  }

  setFloorAttenuation(db) {
    this.building.floorAttenuationDb = db;
  }

  setTool(tool) { this.tool = tool; }
  setMaterial(material) { this.material = material; }
  setSourcePower(p) { this.sourcePower = p; }

  addFloor() {
    this.building.floors.push(emptyFloor());
    this.currentFloor = this.building.floors.length - 1;
    this.lastFloorsResult = null;
    this.render();
  }

  removeCurrentFloor() {
    if (this.building.floors.length <= 1) return;
    this.building.floors.splice(this.currentFloor, 1);
    this.currentFloor = Math.min(this.currentFloor, this.building.floors.length - 1);
    this.lastFloorsResult = null;
    this.render();
  }

  setCurrentFloor(index) {
    if (index < 0 || index >= this.building.floors.length) return;
    this.currentFloor = index;
    if (this.inspectPoint) {
      this.inspectPoint.value = this.getValueAt(this.inspectPoint.xm, this.inspectPoint.ym);
      if (this.onInspect) this.onInspect(this.inspectPoint.value, this.inspectPoint.xm, this.inspectPoint.ym);
    }
    this.render();
  }

  /** dBm value for the currently displayed floor at a point in meters, or
   * null if there's no simulation result yet. */
  getValueAt(xm, ym) {
    const floorPower = this.lastFloorsResult?.[this.currentFloor];
    if (!floorPower || !this.lastGridInfo) return null;
    const { dx, nx, ny } = this.lastGridInfo;
    let ix = Math.round(xm / dx);
    let iy = Math.round(ym / dx);
    ix = Math.min(Math.max(ix, 0), nx - 1);
    iy = Math.min(Math.max(iy, 0), ny - 1);
    return floorPower[iy][ix];
  }

  clearFloor() {
    this.floor.walls = [];
    this.floor.sources = [];
    this.render();
  }

  loadBuilding(building) {
    this.building = {
      width: building.width,
      height: building.height,
      floorAttenuationDb: building.floorAttenuationDb ?? 15,
      floors: building.floors && building.floors.length ? building.floors : [emptyFloor()],
    };
    this.currentFloor = 0;
    this.scale = this._computeScale();
    this._resizeCanvas();
    this.lastFloorsResult = null;
    this.render();
  }

  toMeters(px, py) {
    return [px / this.scale, (this.canvas.height - py) / this.scale];
  }

  toPixels(xm, ym) {
    return [xm * this.scale, this.canvas.height - ym * this.scale];
  }

  _eventToMeters(e) {
    const rect = this.canvas.getBoundingClientRect();
    return this.toMeters(e.clientX - rect.left, e.clientY - rect.top);
  }

  _onMouseDown(e) {
    const [xm, ym] = this._eventToMeters(e);
    if (this.tool === "wall") {
      this.dragStart = [xm, ym];
    } else if (this.tool === "source") {
      this.floor.sources.push({ x: xm, y: ym, power_dbm: this.sourcePower });
      this.render();
    } else if (this.tool === "erase") {
      this._eraseNear(xm, ym);
      this.render();
    } else if (this.tool === "door") {
      this._splitWallForDoor(xm, ym);
      this.render();
    } else if (this.tool === "inspect") {
      const value = this.getValueAt(xm, ym);
      this.inspectPoint = { xm, ym, value };
      this.render();
      if (this.onInspect) this.onInspect(value, xm, ym);
    }
  }

  /** Cut a DOOR_WIDTH-wide opening into the nearest wall at (xm, ym): the
   * wall is replaced by zero, one or two shorter walls with a real gap in
   * between (no wall material there), rather than a distinct "door"
   * object -- the gap itself is what makes it an opening. */
  _splitWallForDoor(xm, ym) {
    const tol = 0.2;
    let best = null;
    let bestDist = Infinity;
    for (const w of this.floor.walls) {
      const d = this._distToSegment(xm, ym, w);
      if (d < bestDist) {
        bestDist = d;
        best = w;
      }
    }
    if (!best || bestDist > tol + best.thickness / 2) return false;

    const dx = best.x2 - best.x1;
    const dy = best.y2 - best.y1;
    const len = Math.hypot(dx, dy);
    if (len < 0.01) return false;
    const ux = dx / len;
    const uy = dy / len;

    let t = (dx * (xm - best.x1) + dy * (ym - best.y1)) / (len * len);
    t = Math.max(0, Math.min(1, t));
    const centerDist = t * len;

    const half = Math.min(DOOR_WIDTH / 2, len / 2 - 0.05);
    if (half <= 0) return false; // wall too short for a door

    const gapStart = centerDist - half;
    const gapEnd = centerDist + half;

    const newWalls = [];
    if (gapStart > 0.05) {
      newWalls.push({
        x1: best.x1,
        y1: best.y1,
        x2: best.x1 + ux * gapStart,
        y2: best.y1 + uy * gapStart,
        material: best.material,
        thickness: best.thickness,
      });
    }
    if (len - gapEnd > 0.05) {
      newWalls.push({
        x1: best.x1 + ux * gapEnd,
        y1: best.y1 + uy * gapEnd,
        x2: best.x2,
        y2: best.y2,
        material: best.material,
        thickness: best.thickness,
      });
    }

    const idx = this.floor.walls.indexOf(best);
    this.floor.walls.splice(idx, 1, ...newWalls);
    return true;
  }

  _onMouseMove(e) {
    if (this.tool === "wall" && this.dragStart) {
      const [xm, ym] = this._eventToMeters(e);
      this.render();
      this._drawPreviewWall(this.dragStart, [xm, ym]);
    }
  }

  _onMouseUp(e) {
    if (this.tool === "wall" && this.dragStart) {
      const [xm, ym] = this._eventToMeters(e);
      const [sx, sy] = this.dragStart;
      if (Math.hypot(xm - sx, ym - sy) > 0.05) {
        this.floor.walls.push({ x1: sx, y1: sy, x2: xm, y2: ym, material: this.material, thickness: 0.15 });
      }
      this.dragStart = null;
      this.render();
    }
  }

  _eraseNear(xm, ym) {
    const tol = 0.15;
    this.floor.sources = this.floor.sources.filter((s) => Math.hypot(s.x - xm, s.y - ym) > tol);
    this.floor.walls = this.floor.walls.filter((w) => this._distToSegment(xm, ym, w) > tol + w.thickness / 2);
  }

  _distToSegment(px, py, w) {
    const dx = w.x2 - w.x1;
    const dy = w.y2 - w.y1;
    const len2 = dx * dx + dy * dy;
    if (len2 === 0) return Math.hypot(px - w.x1, py - w.y1);
    let t = ((px - w.x1) * dx + (py - w.y1) * dy) / len2;
    t = Math.max(0, Math.min(1, t));
    const projx = w.x1 + t * dx;
    const projy = w.y1 + t * dy;
    return Math.hypot(px - projx, py - projy);
  }

  /** floorsPowerDbm: number[][][], range: [min,max] shared across all floors
   * so switching floor tabs doesn't jump the color scale, gridInfo:
   * { dx, nx, ny } needed to map a clicked point back to a grid cell. */
  setResult(floorsPowerDbm, range, gridInfo) {
    this.lastFloorsResult = floorsPowerDbm;
    this.lastRange = range;
    this.lastGridInfo = gridInfo;
    this.render();
  }

  render() {
    const ctx = this.ctx;
    ctx.fillStyle = "#12141a";
    ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

    const floorPower = this.lastFloorsResult?.[this.currentFloor];
    if (floorPower) {
      renderHeatmapToCanvas(floorPower, this.canvas, this.lastRange);
    }

    ctx.strokeStyle = "#555";
    ctx.lineWidth = 1;
    ctx.strokeRect(0.5, 0.5, this.canvas.width - 1, this.canvas.height - 1);

    for (const w of this.floor.walls) this._drawWall(w);
    for (const s of this.floor.sources) this._drawSource(s);
    if (this.inspectPoint) this._drawInspectMarker(this.inspectPoint);
  }

  _drawInspectMarker(point) {
    const [x, y] = this.toPixels(point.xm, point.ym);
    const ctx = this.ctx;
    ctx.save();
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(x - 8, y);
    ctx.lineTo(x + 8, y);
    ctx.moveTo(x, y - 8);
    ctx.lineTo(x, y + 8);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(x, y, 4, 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();
  }

  _drawWall(w) {
    const [x1, y1] = this.toPixels(w.x1, w.y1);
    const [x2, y2] = this.toPixels(w.x2, w.y2);
    const ctx = this.ctx;
    ctx.strokeStyle = MATERIAL_COLORS[w.material] || "#999";
    ctx.lineWidth = Math.max(2, w.thickness * this.scale);
    ctx.lineCap = "round";
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.stroke();
  }

  _drawPreviewWall(start, end) {
    const [x1, y1] = this.toPixels(start[0], start[1]);
    const [x2, y2] = this.toPixels(end[0], end[1]);
    const ctx = this.ctx;
    ctx.save();
    ctx.strokeStyle = "rgba(255,255,255,0.6)";
    ctx.lineWidth = 3;
    ctx.setLineDash([6, 4]);
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.stroke();
    ctx.restore();
  }

  _drawSource(s) {
    const [x, y] = this.toPixels(s.x, s.y);
    const ctx = this.ctx;
    ctx.fillStyle = "#ff5252";
    ctx.beginPath();
    ctx.arc(x, y, 6, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = "#fff";
    ctx.lineWidth = 1.5;
    ctx.stroke();
  }
}
