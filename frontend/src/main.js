import { CanvasEditor } from "./canvas-editor.js?v=3";
import { computeCombinedRange, drawLegend } from "./heatmap-render.js?v=3";
import { fetchMaterials, simulateBuilding } from "./api-client.js?v=3";

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
const floorTabsEl = document.getElementById("floor-tabs");
const addFloorBtn = document.getElementById("add-floor-btn");
const removeFloorBtn = document.getElementById("remove-floor-btn");
const floorAttenuationInput = document.getElementById("floor-attenuation");

const FLOOR_LABELS = ["RDC"];
function floorLabel(i) {
  return FLOOR_LABELS[i] || `Étage ${i}`;
}

function renderFloorTabs() {
  floorTabsEl.innerHTML = "";
  for (let i = 0; i < editor.floorCount; i++) {
    const btn = document.createElement("button");
    btn.textContent = floorLabel(i);
    btn.className = i === editor.currentFloor ? "active" : "";
    btn.addEventListener("click", () => {
      editor.setCurrentFloor(i);
      renderFloorTabs();
    });
    floorTabsEl.appendChild(btn);
  }
  removeFloorBtn.disabled = editor.floorCount <= 1;
}

async function init() {
  drawLegend(legendCanvas);
  renderFloorTabs();
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
floorAttenuationInput.addEventListener("change", () =>
  editor.setFloorAttenuation(parseFloat(floorAttenuationInput.value))
);

function updateDomain() {
  editor.setDomain(parseFloat(widthInput.value), parseFloat(heightInput.value));
}
widthInput.addEventListener("change", updateDomain);
heightInput.addEventListener("change", updateDomain);

clearBtn.addEventListener("click", () => editor.clearFloor());

addFloorBtn.addEventListener("click", () => {
  editor.addFloor();
  renderFloorTabs();
});

removeFloorBtn.addEventListener("click", () => {
  editor.removeCurrentFloor();
  renderFloorTabs();
});

simulateBtn.addEventListener("click", async () => {
  const hasSource = editor.building.floors.some((f) => f.sources.length > 0);
  if (!hasSource) {
    statusEl.textContent = "Ajoute au moins une source (sur un étage) avant de simuler.";
    return;
  }
  statusEl.textContent = "Simulation en cours...";
  simulateBtn.disabled = true;
  try {
    const payload = {
      width: editor.building.width,
      height: editor.building.height,
      floors: editor.building.floors,
      floor_attenuation_db: editor.building.floorAttenuationDb,
      freq_mhz: parseFloat(freqInput.value),
      points_per_wavelength: parseInt(ppwInput.value, 10),
      mode: modeSelect.value,
    };
    const result = await simulateBuilding(payload);
    const range = computeCombinedRange(result.floors_power_dbm);
    editor.setResult(result.floors_power_dbm, range);
    drawLegend(legendCanvas, range);
    statusEl.textContent = `Terminé en ${result.elapsed_s.toFixed(2)}s (grille ${result.nx}x${result.ny}, ${editor.floorCount} étage(s), mode ${result.mode}).`;
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
    building: editor.building,
    freq_mhz: parseFloat(freqInput.value),
    points_per_wavelength: parseInt(ppwInput.value, 10),
    mode: modeSelect.value,
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  downloadBlob(blob, "batiment_mrfdpf.json");
});

importSceneBtn.addEventListener("click", () => importSceneInput.click());

importSceneInput.addEventListener("change", async () => {
  const file = importSceneInput.files[0];
  if (!file) return;
  try {
    const payload = JSON.parse(await file.text());
    const building = payload.building;
    if (!building) throw new Error("fichier invalide: pas de champ 'building'");

    widthInput.value = building.width;
    heightInput.value = building.height;
    floorAttenuationInput.value = building.floorAttenuationDb ?? 15;
    editor.loadBuilding(building);
    renderFloorTabs();

    if (payload.freq_mhz) freqInput.value = payload.freq_mhz;
    if (payload.points_per_wavelength) ppwInput.value = payload.points_per_wavelength;
    if (payload.mode) modeSelect.value = payload.mode;
    statusEl.textContent = "Bâtiment importé.";
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
