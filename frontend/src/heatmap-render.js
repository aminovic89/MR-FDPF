const STOPS = [
  [0.0, [30, 30, 120]],
  [0.35, [0, 170, 200]],
  [0.65, [255, 220, 0]],
  [1.0, [220, 30, 30]],
];

function colorForValue(v, vMin, vMax) {
  const t = Math.min(1, Math.max(0, (v - vMin) / (vMax - vMin || 1)));
  for (let i = 0; i < STOPS.length - 1; i++) {
    const [t0, c0] = STOPS[i];
    const [t1, c1] = STOPS[i + 1];
    if (t >= t0 && t <= t1) {
      const f = (t - t0) / (t1 - t0);
      return c0.map((c, idx) => Math.round(c + f * (c1[idx] - c)));
    }
  }
  return STOPS[STOPS.length - 1][1];
}

/** Range of a power_dbm 2D array, so the color scale always matches the
 * actual scene (absolute dBm depends on tx power, room size and frequency,
 * so a fixed hardcoded range saturates or flattens most scenes). */
export function computeRange(powerDbm) {
  let vMin = Infinity;
  let vMax = -Infinity;
  for (const row of powerDbm) {
    for (const v of row) {
      if (v < vMin) vMin = v;
      if (v > vMax) vMax = v;
    }
  }
  if (!isFinite(vMin) || !isFinite(vMax) || vMin === vMax) {
    vMin = -100;
    vMax = -20;
  }
  return [vMin, vMax];
}

export function renderHeatmapToCanvas(powerDbm, targetCanvas, [vMin, vMax]) {
  const ny = powerDbm.length;
  const nx = powerDbm[0].length;
  const off = document.createElement("canvas");
  off.width = nx;
  off.height = ny;
  const octx = off.getContext("2d");
  const img = octx.createImageData(nx, ny);

  for (let iy = 0; iy < ny; iy++) {
    const rowOut = ny - 1 - iy; // flip: grid row 0 is y=0 (domain bottom)
    for (let ix = 0; ix < nx; ix++) {
      const [r, g, b] = colorForValue(powerDbm[iy][ix], vMin, vMax);
      const idx = (rowOut * nx + ix) * 4;
      img.data[idx] = r;
      img.data[idx + 1] = g;
      img.data[idx + 2] = b;
      img.data[idx + 3] = 210;
    }
  }
  octx.putImageData(img, 0, 0);

  const ctx = targetCanvas.getContext("2d");
  ctx.imageSmoothingEnabled = true;
  ctx.drawImage(off, 0, 0, targetCanvas.width, targetCanvas.height);
}

export function drawLegend(canvas, [vMin, vMax] = [-100, -20]) {
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);
  for (let x = 0; x < w; x++) {
    const t = x / (w - 1);
    const v = vMin + t * (vMax - vMin);
    const [r, g, b] = colorForValue(v, vMin, vMax);
    ctx.fillStyle = `rgb(${r},${g},${b})`;
    ctx.fillRect(x, 0, 1, h * 0.6);
  }
  ctx.fillStyle = "#cbd0d9";
  ctx.font = "11px sans-serif";
  ctx.textAlign = "left";
  ctx.fillText(`${vMin.toFixed(0)} dBm`, 2, h - 2);
  ctx.textAlign = "right";
  ctx.fillText(`${vMax.toFixed(0)} dBm`, w - 2, h - 2);
}
