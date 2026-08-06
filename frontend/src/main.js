import { CanvasEditor } from "./canvas-editor.js";
import { computeRange, drawLegend } from "./heatmap-render.js";
import { fetchMaterials, simulate } from "./api-client.js";

const canvas = document.getElementById("scene-canvas");
const editor = new CanvasEditor(canvas);

const materialSelect = document.getElementById("material-select");
const toolButtons = document.querySelectorAll("[data-tool]");
const widthInput = document.getElementById("domain-width");
const heightInput = document.getElementById("domain-height");
const freqInput = document.getElementById("freq-mhz");
const ppwInput = document.getElementById("ppw");
const modeSelect = document.getElementById("mode-select");
const powerInput = document.getElementById("source-power");
const simulateBtn = document.getElementById("simulate-btn");
const clearBtn = document.getElementById("clear-btn");
const statusEl = document.getElementById("status");
const legendCanvas = document.getElementById("legend-canvas");
const exportSceneBtn = document.getElementById("export-scene-btn");
const importSceneBtn = document.getElementById("import-scene-btn");
const importSceneInput = document.getElementById("import-scene-input");
const exportImageBtn = document.getElementById("export-image-btn");

async function init() {
  drawLegend(legendCanvas);
  try {
    const materials = await fetchMaterials();
    materialSelect.innerHTML = "";
    for (const m of materials) {
      if (m.name === "air") continue;
      const opt = document.createElement("option");
      opt.value = m.name;
      opt.textContent = m.name;
      materialSelect.appendChild(opt);
    }
    materialSelect.value = "concrete";
  } catch (err) {
    statusEl.textContent = `Impossible de charger les matériaux: ${err.message}`;
  }
}

toolButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    toolButtons.forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    editor.setTool(btn.dataset.tool);
  });
});

materialSelect.addEventListener("change", () => editor.setMaterial(materialSelect.value));
powerInput.addEventListener("change", () => editor.setSourcePower(parseFloat(powerInput.value)));

function updateDomain() {
  editor.setDomain(parseFloat(widthInput.value), parseFloat(heightInput.value));
}
widthInput.addEventListener("change", updateDomain);
heightInput.addEventListener("change", updateDomain);

clearBtn.addEventListener("click", () => editor.clearScene());

simulateBtn.addEventListener("click", async () => {
  if (editor.scene.sources.length === 0) {
    statusEl.textContent = "Ajoute au moins une source avant de simuler.";
    return;
  }
  statusEl.textContent = "Simulation en cours...";
  simulateBtn.disabled = true;
  try {
    const payload = {
      width: editor.scene.width,
      height: editor.scene.height,
      walls: editor.scene.walls,
      sources: editor.scene.sources,
      freq_mhz: parseFloat(freqInput.value),
      points_per_wavelength: parseInt(ppwInput.value, 10),
      mode: modeSelect.value,
    };
    const result = await simulate(payload);
    editor.setResult(result);
    drawLegend(legendCanvas, computeRange(result.power_dbm));
    statusEl.textContent = `Terminé en ${result.elapsed_s.toFixed(2)}s (grille ${result.nx}x${result.ny}, mode ${result.mode}).`;
  } catch (err) {
    statusEl.textContent = `Erreur: ${err.message}`;
  } finally {
    simulateBtn.disabled = false;
  }
});

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

exportSceneBtn.addEventListener("click", () => {
  const payload = {
    scene: editor.scene,
    freq_mhz: parseFloat(freqInput.value),
    points_per_wavelength: parseInt(ppwInput.value, 10),
    mode: modeSelect.value,
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  downloadBlob(blob, "scene_mrfdpf.json");
});

importSceneBtn.addEventListener("click", () => importSceneInput.click());

importSceneInput.addEventListener("change", async () => {
  const file = importSceneInput.files[0];
  if (!file) return;
  try {
    const payload = JSON.parse(await file.text());
    const scene = payload.scene || {};
    widthInput.value = scene.width ?? widthInput.value;
    heightInput.value = scene.height ?? heightInput.value;
    editor.setDomain(parseFloat(widthInput.value), parseFloat(heightInput.value));
    editor.scene.walls = scene.walls || [];
    editor.scene.sources = scene.sources || [];
    editor.lastResult = null;
    editor.render();

    if (payload.freq_mhz) freqInput.value = payload.freq_mhz;
    if (payload.points_per_wavelength) ppwInput.value = payload.points_per_wavelength;
    if (payload.mode) modeSelect.value = payload.mode;
    statusEl.textContent = "Scène importée.";
  } catch (err) {
    statusEl.textContent = `Import impossible: ${err.message}`;
  } finally {
    importSceneInput.value = "";
  }
});

exportImageBtn.addEventListener("click", () => {
  canvas.toBlob((blob) => downloadBlob(blob, "couverture_mrfdpf.png"), "image/png");
});

init();
