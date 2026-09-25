import { api } from '../api.js';
import { barChart, donutChart } from '../charts.js';
import { date, disclaimer, escapeHtml, navigate, number, toast } from '../app.js';

export async function renderDashboard(root) {
  const [overview, calibration, device] = await Promise.all([api.overview(), api.calibrations(), api.deviceStatus().catch(() => ({ online: false }))]);
  const classes = overview.class_distribution;
  const classLabels = ['Fibers', 'Fragments', 'Films', 'Pellets', 'Non-plastic'];
  const classValues = [classes.fibers, classes.fragments, classes.films, classes.pellets, classes.non_plastic];
  root.innerHTML = `<div class="action-row"><button id="quick-new">New analysis</button><button id="quick-demo" class="secondary">Run demo</button><span class="chip ${device.online ? 'ok' : 'warn'}">Device ${device.online ? 'online' : 'offline'}</span><span class="chip ${calibration.active ? 'ok' : 'warn'}">${calibration.active ? `${number(calibration.active.mm_per_pixel, 4)} mm/px` : 'Not calibrated'}</span></div>
  <section class="grid kpis" style="margin-top:1rem"><article class="card kpi"><span class="muted">Samples</span><b>${number(overview.total_samples)}</b></article><article class="card kpi"><span class="muted">Particles analysed</span><b>${number(overview.total_particles)}</b></article><article class="card kpi"><span class="muted">Suspected plastic</span><b>${number(overview.suspected_percentage, 1)}%</b></article><article class="card kpi"><span class="muted">Latest concentration</span><b>${overview.latest_concentration_per_l === null ? '—' : `${number(overview.latest_concentration_per_l, 1)}/L`}</b></article></section>
  <section class="grid two-col" style="margin-top:1rem"><article class="card"><h2>Suspected particles over time</h2>${overview.timeline.length ? barChart(overview.timeline.map(item => item.name), overview.timeline.map(item => item.suspected_plastic), { label: 'suspected particle counts over time' }) : '<p class="empty-small">Run an analysis to see trends.</p>'}</article><article class="card"><h2>Overall visual classes</h2>${overview.total_particles ? donutChart(classValues, classLabels) : '<p class="empty-small">No particles analysed.</p>'}</article></section>
  <article class="card" style="margin-top:1rem"><h2>Recent samples</h2>${recentTable(overview.recent_samples)}</article>${disclaimer()}`;
  document.querySelector('#quick-new').onclick = () => navigate('/new');
  document.querySelector('#quick-demo').onclick = async event => {
    event.currentTarget.disabled = true;
    event.currentTarget.textContent = 'Generating…';
    try {
      const result = await api.demo({});
      toast(`Demo analysed ${result.analysis.total_particles} particles`);
      navigate(`/sample/${result.sample.id}`);
    } catch (error) { toast(error.message, true); event.currentTarget.disabled = false; event.currentTarget.textContent = 'Run demo'; }
  };
}

function recentTable(samples) {
  if (!samples.length) return '<p class="empty">No samples yet. Start an upload or synthetic demo.</p>';
  return `<div class="table-wrap"><table class="table"><thead><tr><th>Sample</th><th>Date</th><th>Suspected</th><th>Total</th><th>Concentration</th></tr></thead><tbody>${samples.map(sample => `<tr><td><a href="#/sample/${sample.id}">${escapeHtml(sample.name)}</a></td><td>${date(sample.created_at)}</td><td>${number(sample.suspected_plastic)}</td><td>${number(sample.total_particles)}</td><td>${sample.concentration_per_l === null ? '—' : `${number(sample.concentration_per_l, 1)}/L`}</td></tr>`).join('')}</tbody></table></div>`;
}
