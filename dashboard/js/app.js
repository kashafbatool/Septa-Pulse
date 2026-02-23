/**
 * app.js — Main application controller.
 *
 * Orchestrates API calls, map updates, chart updates, and filter state.
 */

const REFRESH_INTERVAL_MS = 30_000;

let state = {
  mode: "",
  route: "",
  layer: "live",
};

// ─── Header stats ─────────────────────────────────────────────

async function refreshSummary() {
  try {
    const data = await fetchSummary();
    document.getElementById("stat-live").textContent = data.live_vehicle_count ?? "—";
    document.getElementById("stat-delayed").textContent = data.delayed_vehicle_count ?? "—";
    document.getElementById("stat-24h").textContent = formatCount(data.positions_last_24h);
    const t = new Date(data.as_of);
    document.getElementById("stat-update").textContent = t.toLocaleTimeString();
  } catch (e) {
    console.warn("Summary fetch failed:", e);
  }
}

function formatCount(n) {
  if (!n) return "—";
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
  return String(n);
}

// ─── Map refresh ─────────────────────────────────────────────

async function refreshMap() {
  setPulse("active");
  try {
    if (state.layer === "live") {
      const data = await fetchLiveVehicles(state.mode, state.route);
      console.log("[SEPTA Pulse] live vehicles:", data.count, data);
      updateLiveMarkers(data);
    } else {
      const data = await fetchHeatmap(24, state.mode);
      console.log("[SEPTA Pulse] heatmap features:", data.count);
      updateHeatmap(data);
    }
  } catch (e) {
    console.error("[SEPTA Pulse] Map refresh failed:", e);
    setPulse("stale");
  }
}

// ─── Charts refresh ───────────────────────────────────────────

async function refreshCharts() {
  try {
    const data = await fetchDelays(24, state.mode);
    updateDelayChart(data);
    updateOntimeChart(data);
  } catch (e) {
    console.warn("Charts refresh failed:", e);
  }
}

// ─── Route list ───────────────────────────────────────────────

async function refreshRoutes() {
  try {
    const data = await fetchRoutes(state.mode);
    populateRouteSelect(data.routes || []);
  } catch (e) {
    console.warn("Routes fetch failed:", e);
  }
}

// ─── Pulse indicator ─────────────────────────────────────────

function setPulse(status) {
  const dot = document.getElementById("pulse-dot");
  dot.className = "pulse-dot" + (status === "stale" ? " stale" : "");
}

// ─── Filter wiring ────────────────────────────────────────────

document.getElementById("mode-filter").addEventListener("click", (e) => {
  const btn = e.target.closest(".btn-mode");
  if (!btn) return;
  document.querySelectorAll("#mode-filter .btn-mode").forEach((b) => b.classList.remove("active"));
  btn.classList.add("active");
  state.mode = btn.dataset.mode;
  state.route = "";
  document.getElementById("route-select").value = "";
  refreshAll();
  refreshRoutes();
});

document.getElementById("layer-toggle").addEventListener("click", (e) => {
  const btn = e.target.closest(".btn-mode");
  if (!btn) return;
  document.querySelectorAll("#layer-toggle .btn-mode").forEach((b) => b.classList.remove("active"));
  btn.classList.add("active");
  state.layer = btn.dataset.layer;
  setLayer(state.layer);
  refreshMap();
});

document.getElementById("route-select").addEventListener("change", (e) => {
  state.route = e.target.value;
  if (state.layer === "live") refreshMap();
});

// ─── Refresh all ─────────────────────────────────────────────

async function refreshAll() {
  await Promise.allSettled([refreshMap(), refreshCharts(), refreshSummary()]);
}

// ─── Bootstrap ───────────────────────────────────────────────

(async function init() {
  // Initial load
  await refreshAll();
  await refreshRoutes();

  // Scheduled refresh
  setInterval(refreshAll, REFRESH_INTERVAL_MS);
})();
