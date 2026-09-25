import { api } from '../api.js';
import { barChart } from '../charts.js';
import { date, disclaimer, escapeHtml, number, toast } from '../app.js';

export async function renderMl(root) {
  const status = await api.modelStatus();
  render(status);

  function render(model) {
    root.innerHTML = `<section class="page-head"><div><h1>ML lab</h1><p class="muted">The classifier estimates visual shape categories from image features. It does not chemically identify materials.</p></div><span class="chip ${model.source ? 'ok' : 'warn'}">${escapeHtml(model.source || 'No trained model')}</span></section>
      <section class="grid two-col"><article class="card"><h2>Model status</h2>${model.source ? `<dl class="form-grid"><div><dt class="muted">Training source</dt><dd>${escapeHtml(model.source)}</dd></div><div><dt class="muted">Trained</dt><dd>${date(model.trained_at)}</dd></div><div><dt class="muted">Samples</dt><dd>${number(model.sample_count)}</dd></div><div><dt class="muted">Classes</dt><dd>${(model.classes || []).map(escapeHtml).join(', ') || '—'}</dd></div></dl>` : '<p class="warning">No model has been trained yet. Train a starter model before using ML or hybrid classification.</p>'}</article>
        <article class="card"><h2>Retrain model</h2><form id="train-model"><div class="field"><label><input id="include-synthetic" type="checkbox" checked> Include synthetic feature data</label></div><div class="field"><label><input id="include-verified" type="checkbox" checked> Include user-verified particle classes</label></div><p class="muted">Synthetic data is suitable for demonstrating the workflow. Diverse, verified reference data is required for meaningful real-world estimates.</p><div class="form-actions"><button type="submit">Train model</button></div></form></article></section>
      <section id="metrics" style="margin-top:1rem">${metrics(model)}</section>${disclaimer()}`;

    root.querySelector('#train-model').onsubmit = async event => {
      event.preventDefault();
      const includeSynthetic = root.querySelector('#include-synthetic').checked;
      const includeVerified = root.querySelector('#include-verified').checked;
      if (!includeSynthetic && !includeVerified) {
        toast('Include synthetic data, verified particles, or both.', true);
        return;
      }
      const button = event.currentTarget.querySelector('button');
      button.disabled = true;
      button.textContent = 'Training…';
      try {
        const updated = await api.trainModel({ include_synthetic: includeSynthetic, include_verified_particles: includeVerified });
        toast('Model training complete');
        render(updated);
      } catch (error) { toast(error.message, true); button.disabled = false; button.textContent = 'Train model'; }
    };
  }
}

function metrics(model) {
  const metrics = model.metrics;
  if (!metrics) return '<article class="card empty"><p>Training metrics will appear here after a model is available.</p></article>';
  const classes = model.classes || [];
  const featureEntries = Object.entries(metrics.feature_importance || {}).sort(([, left], [, right]) => right - left).slice(0, 12);
  return `<section class="grid two-col"><article class="card"><h2>Validation metrics</h2><div class="summary-grid"><div class="summary-item"><span>Accuracy</span><b>${number(metrics.accuracy * 100, 1)}%</b></div><div class="summary-item"><span>Classes</span><b>${classes.length}</b></div></div><div class="table-wrap" style="margin-top:1rem"><table class="table"><thead><tr><th>Class</th><th>Precision</th><th>Recall</th><th>F1</th></tr></thead><tbody>${classes.map(label => `<tr><td>${escapeHtml(label)}</td><td>${number((metrics.precision || {})[label], 3)}</td><td>${number((metrics.recall || {})[label], 3)}</td><td>${number((metrics.f1 || {})[label], 3)}</td></tr>`).join('')}</tbody></table></div></article>
    <article class="card"><h2>Feature importance</h2>${featureEntries.length ? barChart(featureEntries.map(([name]) => name), featureEntries.map(([, value]) => Number((value * 100).toFixed(2))), { label: 'Feature importance percentages' }) : '<p class="empty-small">No feature importances available.</p>'}</article></section>
    <article class="card" style="margin-top:1rem"><h2>Confusion matrix</h2>${confusionMatrix(classes, metrics.confusion_matrix || [])}<p class="muted">Rows show the reference visual class; columns show the predicted visual class. Accuracy depends on dataset quality and diversity.</p></article>`;
}

function confusionMatrix(classes, matrix) {
  if (!classes.length || !matrix.length) return '<p class="empty-small">No confusion-matrix data available.</p>';
  const maximum = Math.max(...matrix.flat(), 1);
  return `<div class="table-wrap"><table class="table"><thead><tr><th>Actual / predicted</th>${classes.map(label => `<th>${escapeHtml(label)}</th>`).join('')}</tr></thead><tbody>${matrix.map((row, index) => `<tr><th>${escapeHtml(classes[index] || String(index))}</th>${row.map(value => `<td style="background:color-mix(in srgb, var(--accent) ${Math.round(value / maximum * 38)}%, transparent)">${number(value)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
}
