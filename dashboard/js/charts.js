/**
 * charts.js — Chart.js visualizations for delay rankings and on-time performance.
 */

Chart.defaults.color = "#94a3b8";
Chart.defaults.borderColor = "#1e293b";
Chart.defaults.font.family = "Inter, system-ui, sans-serif";

let delayChart = null;
let ontimeChart = null;

// ─── Delay bar chart ─────────────────────────────────────────

function initDelayChart() {
  const ctx = document.getElementById("delay-chart").getContext("2d");
  delayChart = new Chart(ctx, {
    type: "bar",
    data: { labels: [], datasets: [] },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const sec = ctx.parsed.x;
              if (sec == null) return "No data";
              const min = (sec / 60).toFixed(1);
              return `Avg delay: ${min} min`;
            },
          },
        },
      },
      scales: {
        x: {
          grid: { color: "#1e293b" },
          ticks: { color: "#94a3b8", font: { size: 11 } },
          title: { display: true, text: "Avg delay (sec)", color: "#64748b" },
        },
        y: {
          grid: { display: false },
          ticks: { color: "#e2e8f0", font: { size: 11 } },
        },
      },
    },
  });
}

function updateDelayChart(data) {
  if (!delayChart) initDelayChart();

  const routes = (data.routes || []).slice(0, 15);
  const labels = routes.map((r) => r.route);
  const values = routes.map((r) => r.avg_delay_sec || 0);
  const colors = values.map((v) =>
    v > 600 ? "#ef4444" : v > 300 ? "#f59e0b" : "#22c55e"
  );

  delayChart.data.labels = labels;
  delayChart.data.datasets = [
    {
      data: values,
      backgroundColor: colors,
      borderRadius: 4,
      borderSkipped: false,
    },
  ];
  delayChart.update("active");

  // Dynamic height based on number of routes
  const canvas = document.getElementById("delay-chart");
  canvas.parentElement.style.height = Math.max(200, labels.length * 28) + "px";
}

// ─── On-time doughnut chart ───────────────────────────────────

function initOntimeChart() {
  const ctx = document.getElementById("ontime-chart").getContext("2d");
  ontimeChart = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: ["On Time", "Delayed"],
      datasets: [
        {
          data: [0, 0],
          backgroundColor: ["#22c55e", "#ef4444"],
          borderWidth: 0,
          hoverOffset: 6,
        },
      ],
    },
    options: {
      responsive: true,
      cutout: "68%",
      plugins: {
        legend: {
          position: "bottom",
          labels: { color: "#94a3b8", font: { size: 11 }, padding: 10 },
        },
        tooltip: {
          callbacks: {
            label: (ctx) => ` ${ctx.parsed.toFixed(1)}%`,
          },
        },
      },
    },
  });
}

function updateOntimeChart(delayData) {
  if (!ontimeChart) initOntimeChart();

  const routes = delayData.routes || [];
  if (!routes.length) return;

  // Average on-time pct across all routes
  const validRoutes = routes.filter((r) => r.on_time_pct != null);
  if (!validRoutes.length) return;

  const avgOnTime = validRoutes.reduce((s, r) => s + r.on_time_pct, 0) / validRoutes.length;
  const avgLate = 100 - avgOnTime;

  ontimeChart.data.datasets[0].data = [
    parseFloat(avgOnTime.toFixed(1)),
    parseFloat(avgLate.toFixed(1)),
  ];
  ontimeChart.update("active");
}
