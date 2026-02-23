/**
 * map.js — Leaflet map: live vehicle markers + historical heatmap layer.
 */

// Philadelphia center
const PHILLY = [39.9526, -75.1652];
const DEFAULT_ZOOM = 12;

const map = L.map("map", {
  center: PHILLY,
  zoom: DEFAULT_ZOOM,
  zoomControl: false,
});
L.control.zoom({ position: "bottomright" }).addTo(map);

// Dark CartoDB tile layer
L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
  attribution:
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
  maxZoom: 19,
}).addTo(map);

// State
let vehicleMarkers = {};   // vehicle_id → L.CircleMarker
let heatLayer = null;
let currentLayer = "live"; // 'live' | 'heatmap'

// ─── Marker helpers ──────────────────────────────────────────

const MODE_COLORS = {
  bus:     "#005daa",
  trolley: "#7c3aed",
  rail:    "#f59e0b",
};

function getColor(mode) {
  return MODE_COLORS[mode] || "#38bdf8";
}

function makeMarker(vehicle) {
  const color = getColor(vehicle.mode);
  const radius = vehicle.mode === "rail" ? 8 : 6;

  const marker = L.circleMarker([vehicle.lat, vehicle.lon], {
    radius,
    color,
    fillColor: color,
    fillOpacity: 0.85,
    weight: 1.5,
    opacity: 1,
  });

  marker.bindPopup(() => buildPopup(vehicle), { maxWidth: 240 });
  return marker;
}

function buildPopup(v) {
  const delay = formatDelay(v.offset_sec);
  const delayClass = v.offset_sec == null
    ? "" : v.offset_sec > 300 ? "popup-late"
    : v.offset_sec < -60 ? "popup-early" : "popup-ontime";

  return `
    <div class="popup-route">Route ${v.route}</div>
    <div class="popup-dest">${v.destination || "—"}</div>
    <div class="popup-row">
      <span class="popup-key">Mode</span>
      <span class="popup-val">${capitalize(v.mode)}</span>
    </div>
    <div class="popup-row">
      <span class="popup-key">Vehicle</span>
      <span class="popup-val">${v.vehicle_id}</span>
    </div>
    <div class="popup-row">
      <span class="popup-key">Delay</span>
      <span class="popup-val ${delayClass}">${delay}</span>
    </div>
    ${v.speed != null ? `
    <div class="popup-row">
      <span class="popup-key">Speed</span>
      <span class="popup-val">${v.speed.toFixed(1)} mph</span>
    </div>` : ""}
    ${v.heading != null ? `
    <div class="popup-row">
      <span class="popup-key">Heading</span>
      <span class="popup-val">${v.heading}°</span>
    </div>` : ""}
  `;
}

function formatDelay(sec) {
  if (sec == null) return "Unknown";
  if (Math.abs(sec) < 60) return "On time";
  const min = Math.round(Math.abs(sec) / 60);
  return sec > 0 ? `${min} min late` : `${min} min early`;
}

function capitalize(s) {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : s;
}

// ─── Live vehicles ───────────────────────────────────────────

function updateLiveMarkers(data) {
  const seen = new Set();

  (data.vehicles || []).forEach((v) => {
    if (!v.lat || !v.lon) return; // skip records without coordinates
    seen.add(v.vehicle_id);

    try {
      if (vehicleMarkers[v.vehicle_id]) {
        vehicleMarkers[v.vehicle_id]
          .setLatLng([v.lat, v.lon])
          .setPopupContent(buildPopup(v));
      } else {
        const marker = makeMarker(v);
        marker.addTo(map);
        vehicleMarkers[v.vehicle_id] = marker;
      }
    } catch (e) {
      console.warn("[SEPTA Pulse] Failed to render vehicle", v.vehicle_id, e);
    }
  });

  // Remove stale markers
  Object.keys(vehicleMarkers).forEach((id) => {
    if (!seen.has(id)) {
      map.removeLayer(vehicleMarkers[id]);
      delete vehicleMarkers[id];
    }
  });
}

function clearLiveMarkers() {
  Object.values(vehicleMarkers).forEach((m) => map.removeLayer(m));
  vehicleMarkers = {};
}

// ─── Heatmap ─────────────────────────────────────────────────

function updateHeatmap(geojson) {
  if (heatLayer) {
    map.removeLayer(heatLayer);
    heatLayer = null;
  }

  const points = (geojson.features || []).map((f) => {
    const [lon, lat] = f.geometry.coordinates;
    const intensity = f.properties.offset_sec
      ? Math.min(1, Math.abs(f.properties.offset_sec) / 1800)
      : 0.3;
    return [lat, lon, intensity];
  });

  if (points.length > 0) {
    heatLayer = L.heatLayer(points, {
      radius: 18,
      blur: 20,
      maxZoom: 17,
      gradient: { 0.2: "#005daa", 0.5: "#f59e0b", 1.0: "#ef4444" },
    }).addTo(map);
  }
}

function clearHeatmap() {
  if (heatLayer) {
    map.removeLayer(heatLayer);
    heatLayer = null;
  }
}

// ─── Layer switching ─────────────────────────────────────────

function setLayer(layer) {
  currentLayer = layer;
  if (layer === "heatmap") {
    clearLiveMarkers();
  } else {
    clearHeatmap();
  }
}

// ─── Route list ──────────────────────────────────────────────

function populateRouteSelect(routes) {
  const sel = document.getElementById("route-select");
  const current = sel.value;
  sel.innerHTML = '<option value="">All routes</option>';
  routes.forEach((r) => {
    const opt = document.createElement("option");
    opt.value = r.route;
    opt.textContent = `${r.route} (${r.mode})`;
    sel.appendChild(opt);
  });
  if (current) sel.value = current;
}
