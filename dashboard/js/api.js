/**
 * api.js — Fetch helpers for the SEPTA Pulse FastAPI backend.
 *
 * All functions return parsed JSON or throw an Error.
 * The API_BASE defaults to localhost for local dev; in production
 * set window.SEPTA_API_BASE before this script loads.
 */

const API_BASE = window.SEPTA_API_BASE || "http://localhost:8000";

async function apiFetch(path, params = {}) {
  const url = new URL(API_BASE + path);
  Object.entries(params).forEach(([k, v]) => {
    if (v !== null && v !== undefined && v !== "") url.searchParams.set(k, v);
  });
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error(`API ${res.status}: ${path}`);
  return res.json();
}

/** Current vehicle positions (last 90s). */
async function fetchLiveVehicles(mode = "", route = "") {
  return apiFetch("/api/vehicles/live", { mode, route });
}

/** Historical trail for a route. */
async function fetchVehicleHistory(route, hours = 6) {
  return apiFetch("/api/vehicles/history", { route, hours });
}

/** All known routes. */
async function fetchRoutes(mode = "") {
  return apiFetch("/api/vehicles/routes", { mode });
}

/** Delay rankings per route. */
async function fetchDelays(hours = 24, mode = "") {
  return apiFetch("/api/analytics/delays", { hours, mode });
}

/** GeoJSON heatmap data. */
async function fetchHeatmap(hours = 24, mode = "") {
  return apiFetch("/api/analytics/heatmap", { hours, mode });
}

/** On-time efficiency per route. */
async function fetchRouteEfficiency(hours = 24) {
  return apiFetch("/api/analytics/route-efficiency", { hours });
}

/** Dashboard summary stats. */
async function fetchSummary() {
  return apiFetch("/api/analytics/summary");
}
