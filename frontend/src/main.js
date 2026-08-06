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

init();
