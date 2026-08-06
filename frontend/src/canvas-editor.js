import { computeRange, renderHeatmapToCanvas } from "./heatmap-render.js";

const MATERIAL_COLORS = {
  concrete: "#8a8a8a",
  brick: "#b5651d",
  drywall: "#d8c9a3",
  glass: "#7ec8e3",
  wood: "#a0703a",
  metal: "#c7c9d1",
};

const MAX_CANVAS_DIM = 700;

export class CanvasEditor {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.scene = { width: 8, height: 6, walls: [], sources: [] };
    this.tool = "wall";
    this.material = "concrete";
    this.sourcePower = 20;
    this.lastResult = null;
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

  _computeScale() {
    const scale = MAX_CANVAS_DIM / Math.max(this.scene.width, this.scene.height);
    return Math.max(15, Math.min(120, scale));
  }

  _resizeCanvas() {
    this.canvas.width = Math.round(this.scene.width * this.scale);
    this.canvas.height = Math.round(this.scene.height * this.scale);
  }

  setDomain(width, height) {
    this.scene.width = width;
    this.scene.height = height;
    this.scale = this._computeScale();
    this._resizeCanvas();
    this.lastResult = null;
    this.render();
  }

  setTool(tool) { this.tool = tool; }
  setMaterial(material) { this.material = material; }
  setSourcePower(p) { this.sourcePower = p; }

  clearScene() {
    this.scene.walls = [];
    this.scene.sources = [];
    this.lastResult = null;
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
      this.scene.sources.push({ x: xm, y: ym, power_dbm: this.sourcePower });
      this.render();
    } else if (this.tool === "erase") {
      this._eraseNear(xm, ym);
      this.render();
    }
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
        this.scene.walls.push({ x1: sx, y1: sy, x2: xm, y2: ym, material: this.material, thickness: 0.15 });
      }
      this.dragStart = null;
      this.render();
    }
  }

  _eraseNear(xm, ym) {
    const tol = 0.15;
    this.scene.sources = this.scene.sources.filter((s) => Math.hypot(s.x - xm, s.y - ym) > tol);
    this.scene.walls = this.scene.walls.filter((w) => this._distToSegment(xm, ym, w) > tol + w.thickness / 2);
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

  setResult(result) {
    this.lastResult = result;
    this.lastRange = computeRange(result.power_dbm);
    this.render();
  }

  render() {
    const ctx = this.ctx;
    ctx.fillStyle = "#12141a";
    ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

    if (this.lastResult) {
      renderHeatmapToCanvas(this.lastResult.power_dbm, this.canvas, this.lastRange);
    }

    ctx.strokeStyle = "#555";
    ctx.lineWidth = 1;
    ctx.strokeRect(0.5, 0.5, this.canvas.width - 1, this.canvas.height - 1);

    for (const w of this.scene.walls) this._drawWall(w);
    for (const s of this.scene.sources) this._drawSource(s);
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
