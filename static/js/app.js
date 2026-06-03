/* ── 1. MODAL MANAGEMENT ── */

function openModal() {
  document.getElementById("modal-overlay").classList.remove("hidden");
  document.getElementById("modal-overlay").classList.add("visible");
}

function closeModal() {
  document.getElementById("modal-overlay").classList.add("hidden");
  document.getElementById("modal-overlay").classList.remove("visible");
  document.getElementById("modal-content").innerHTML = "";
}

document.addEventListener("DOMContentLoaded", () => {
  const overlay = document.getElementById("modal-overlay");
  if (overlay) {
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) closeModal();
    });
  }
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeModal();
});

/* ── 2. TOAST NOTIFICATION SYSTEM ── */

function showToast(message, type = "success") {
  const existing = document.getElementById("toast");
  if (existing) existing.remove();

  const toast = document.createElement("div");
  toast.id = "toast";
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  document.body.appendChild(toast);

  setTimeout(() => toast.classList.add("toast-visible"), 10);
  setTimeout(() => {
    toast.classList.remove("toast-visible");
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

/* ── 3. HTMX EVENT LISTENERS ── */

document.addEventListener("closeModal", () => closeModal());

document.addEventListener("showToast", (e) => {
  showToast(e.detail.value);
});

document.addEventListener("refreshDashboard", () => {
  const cards = document.getElementById("dashboard-cards");
  const summary = document.getElementById("summary-panel");
  const form = document.getElementById("dashboard-filter-form");
  if (cards) htmx.trigger(cards, "refresh");
  if (form) htmx.trigger(form, "submit");
  if (summary) htmx.trigger(summary, "refresh");
});

document.addEventListener("refreshExpenseList", () => {
  const form = document.getElementById("expense-filter-form");
  if (form) htmx.trigger(form, "submit");
});

document.body.addEventListener("htmx:responseError", (e) => {
  if (e.detail.xhr.status === 404) {
    alert("This expense no longer exists.");
  }
});

/* ── 4. CHART INITIALIZATION ── */

const chartInstances = {};

const CATEGORY_COLORS = {
  Food: "#059669",
  Transport: "#2563eb",
  Shopping: "#7c3aed",
  Bills: "#ea580c",
  Entertainment: "#0d9488",
  Health: "#c026d3",
  Education: "#0284c7",
  Other: "#64748b",
};

function destroyCharts() {
  Object.keys(chartInstances).forEach((key) => {
    if (chartInstances[key]) {
      chartInstances[key].destroy();
      delete chartInstances[key];
    }
  });
}

function formatInrTick(value) {
  return `₹${Number(value).toLocaleString("en-IN")}`;
}

function initCharts() {
  if (typeof Chart === "undefined") return;

  Chart.defaults.color = "#64748b";
  Chart.defaults.borderColor = "rgba(148,163,184,0.25)";
  Chart.defaults.font.family = "'Segoe UI', system-ui, -apple-system, sans-serif";

  destroyCharts();

  const pieCanvas = document.getElementById("pie-chart");
  if (pieCanvas) {
    const breakdown = JSON.parse(pieCanvas.dataset.breakdown || "{}");
    const labels = Object.keys(breakdown).filter((k) => breakdown[k] > 0);
    const values = labels.map((k) => parseFloat(breakdown[k]));
    const colors = labels.map((k) => CATEGORY_COLORS[k] || "#94a3b8");

    chartInstances.pie = new Chart(pieCanvas, {
      type: "doughnut",
      data: {
        labels,
        datasets: [{ data: values, backgroundColor: colors, borderWidth: 2, borderColor: "#fff" }],
      },
      options: {
        cutout: "62%",
        plugins: {
          legend: { position: "right", labels: { padding: 14, usePointStyle: true } },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
                const pct = total ? Math.round((ctx.parsed / total) * 100) : 0;
                return ` ${ctx.label}: ₹${ctx.parsed.toLocaleString("en-IN")} (${pct}%)`;
              },
            },
          },
        },
      },
    });
  }

  const lineCanvas = document.getElementById("line-chart");
  if (lineCanvas) {
    const daily = JSON.parse(lineCanvas.dataset.daily || "{}");
    const labels = Object.keys(daily).map((d) => `Day ${d}`);
    const values = Object.values(daily).map((v) => parseFloat(v));

    chartInstances.line = new Chart(lineCanvas, {
      type: "line",
      data: {
        labels,
        datasets: [{
          label: "Daily Spending",
          data: values,
          borderColor: "#4f46e5",
          backgroundColor: "rgba(79,70,229,0.12)",
          fill: true,
          tension: 0.35,
          pointRadius: 2,
          pointHoverRadius: 5,
          borderWidth: 2.5,
        }],
      },
      options: {
        scales: {
          y: { beginAtZero: true, ticks: { callback: formatInrTick }, grid: { color: "rgba(148,163,184,0.15)" } },
          x: { grid: { display: false } },
        },
        plugins: { legend: { display: false } },
      },
    });
  }

  const barCanvas = document.getElementById("bar-chart");
  if (barCanvas) {
    const labels = JSON.parse(barCanvas.dataset.labels || "[]");
    const values = JSON.parse(barCanvas.dataset.values || "[]");

    chartInstances.bar = new Chart(barCanvas, {
      type: "bar",
      data: {
        labels,
        datasets: [{
          label: "Monthly Total",
          data: values,
          backgroundColor: "rgba(79,70,229,0.75)",
          borderRadius: 6,
          borderSkipped: false,
        }],
      },
      options: {
        scales: {
          y: { beginAtZero: true, ticks: { callback: formatInrTick } },
          x: { grid: { display: false } },
        },
        plugins: { legend: { display: false } },
      },
    });
  }

  const trendCanvas = document.getElementById("trend-chart");
  if (trendCanvas) {
    const labels = JSON.parse(trendCanvas.dataset.labels || "[]");
    const values = JSON.parse(trendCanvas.dataset.values || "[]");

    chartInstances.trend = new Chart(trendCanvas, {
      type: "line",
      data: {
        labels,
        datasets: [{
          label: "Spending Trend",
          data: values,
          borderColor: "#0d9488",
          backgroundColor: "rgba(13,148,136,0.1)",
          fill: true,
          tension: 0.4,
          pointRadius: 4,
          pointBackgroundColor: "#0d9488",
          borderWidth: 2.5,
        }],
      },
      options: {
        scales: {
          y: { beginAtZero: true, ticks: { callback: formatInrTick } },
          x: { grid: { display: false } },
        },
        plugins: { legend: { display: false } },
      },
    });
  }
}

document.addEventListener("DOMContentLoaded", initCharts);

document.body.addEventListener("htmx:afterSwap", (e) => {
  if (e.detail.target && e.detail.target.id === "dashboard-charts-panel") {
    initCharts();
  }
});
