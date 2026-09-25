import { escapeHtml } from './app.js';

const palette = ['#0b7285', '#2673dd', '#8e4ec6', '#36a269', '#788897', '#d8811b'];
let chartId = 0;

function chartCanvas(config, label) {
  const id = `chart-${++chartId}`;
  queueMicrotask(() => {
    const canvas = document.getElementById(id);
    if (!canvas || !window.Chart) return;
    new window.Chart(canvas, config);
  });
  return `<div class="chart-canvas"><canvas id="${id}" role="img" aria-label="${escapeHtml(label)}"></canvas></div>`;
}

export function barChart(labels, values, options = {}) {
  const label = options.label || 'Bar chart';
  return chartCanvas({
    type: 'bar',
    data: {
      labels,
      datasets: [{ label, data: values, backgroundColor: values.map((_, index) => palette[index % palette.length]), borderRadius: 5 }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: context => `${context.parsed.y}` } } },
      scales: { y: { beginAtZero: true, ticks: { precision: 0 } }, x: { ticks: { maxRotation: 35, minRotation: 0 } } },
    },
  }, label);
}

export function donutChart(values, labels) {
  const total = values.reduce((sum, value) => sum + Number(value || 0), 0);
  const chart = chartCanvas({
    type: 'doughnut',
    data: { labels, datasets: [{ data: values, backgroundColor: values.map((_, index) => palette[index % palette.length]), borderWidth: 0 }] },
    options: { responsive: true, maintainAspectRatio: false, cutout: '64%', plugins: { legend: { display: false } } },
  }, 'Visual class distribution');
  return `<div class="donut-wrap">${chart}<ul class="legend">${labels.map((label, index) => `<li><i style="background:${palette[index % palette.length]}"></i>${escapeHtml(label)} <b>${values[index] || 0}</b></li>`).join('')}</ul><span class="sr-only">${total} particles</span></div>`;
}

export function scatterChart(items) {
  if (!items.length) return '<p class="empty-small">No particle data.</p>';
  const colour = { fiber: palette[0], fragment: palette[1], film: palette[2], pellet: palette[3], non_plastic: palette[4] };
  return chartCanvas({
    type: 'scatter',
    data: {
      datasets: [{
        label: 'Particles',
        data: items.map(item => ({ x: Number(item.aspect_ratio), y: Number(item.length_mm ?? item.length_px), particle: item })),
        pointRadius: 4,
        pointBackgroundColor: items.map(item => colour[item.shape_class] || palette[4]),
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: context => `${context.raw.particle.shape_class} #${context.raw.particle.idx}: ${context.parsed.x.toFixed(2)} ratio, ${context.parsed.y.toFixed(3)} length` } } },
      scales: { x: { title: { display: true, text: 'Aspect ratio' }, beginAtZero: true }, y: { title: { display: true, text: 'Length' }, beginAtZero: true } },
    },
  }, 'Aspect ratio versus particle length');
}
