import { api } from '../api.js';
import { barChart } from '../charts.js';
import { date, disclaimer, escapeHtml, number, toast } from '../app.js';

const PAGE_SIZE = 20;

export async function renderHistory(root) {
  const state = { search: '', sort: 'created_at', order: 'desc', date: '', page: 1, selected: new Set() };

  async function load() {
    root.innerHTML = '<div class="loading"><i class="spinner"></i><span>Loading sample history…</span></div>';
    const first = await api.samples({ search: state.search, page: 1, per_page: 100, sort: state.sort, order: state.order });
    const remainingPages = Math.ceil(first.total / first.per_page);
    const rest = await Promise.all(Array.from({ length: Math.max(0, remainingPages - 1) }, (_, index) => api.samples({
      search: state.search, page: index + 2, per_page: 100, sort: state.sort, order: state.order,
    })));
    let samples = [first, ...rest].flatMap(page => page.items);
    if (state.date) samples = samples.filter(sample => String(sample.created_at).slice(0, 10) === state.date);
    const totalPages = Math.max(1, Math.ceil(samples.length / PAGE_SIZE));
    state.page = Math.min(state.page, totalPages);
    const visible = samples.slice((state.page - 1) * PAGE_SIZE, state.page * PAGE_SIZE);
    render(samples, visible, totalPages);
  }

  function render(samples, visible, totalPages) {
    root.innerHTML = `<section class="page-head"><div><h1>Sample history</h1><p class="muted">Compare optical screening results and manage locally stored samples.</p></div><div class="action-row"><button id="compare-samples" class="secondary" type="button" ${state.selected.size < 2 ? 'disabled' : ''}>Compare selected (${state.selected.size})</button><button id="delete-selected" class="danger" type="button" ${state.selected.size ? '' : 'disabled'}>Delete selected</button></div></section>
      <article class="card"><form id="history-filters" class="filters"><div class="field"><label for="history-search">Search</label><input id="history-search" value="${escapeHtml(state.search)}" placeholder="Name or location"></div><div class="field"><label for="history-date">Date</label><input id="history-date" type="date" value="${escapeHtml(state.date)}"></div><div class="field"><label for="history-sort">Sort by</label><select id="history-sort"><option value="created_at">Date</option><option value="name">Name</option><option value="suspected_plastic">Suspected count</option><option value="total_particles">Particle count</option></select></div><div class="field"><label for="history-order">Direction</label><select id="history-order"><option value="desc">Newest / highest</option><option value="asc">Oldest / lowest</option></select></div><div class="form-actions"><button type="submit">Apply</button><button id="clear-history-filters" class="secondary" type="button">Clear</button></div></form></article>
      <article id="comparison" class="card hide" style="margin-top:1rem"></article>
      <article class="card" style="margin-top:1rem">${table(visible, state.selected)}<div class="pagination"><span>${samples.length} matching sample${samples.length === 1 ? '' : 's'}</span><span><button id="previous-page" class="secondary" type="button" ${state.page <= 1 ? 'disabled' : ''}>Previous</button> Page ${state.page} of ${totalPages} <button id="next-page" class="secondary" type="button" ${state.page >= totalPages ? 'disabled' : ''}>Next</button></span></div></article>${disclaimer()}`;
    root.querySelector('#history-sort').value = state.sort;
    root.querySelector('#history-order').value = state.order;

    root.querySelector('#history-filters').onsubmit = event => {
      event.preventDefault();
      state.search = root.querySelector('#history-search').value.trim();
      state.date = root.querySelector('#history-date').value;
      state.sort = root.querySelector('#history-sort').value;
      state.order = root.querySelector('#history-order').value;
      state.page = 1;
      load().catch(showError);
    };
    root.querySelector('#clear-history-filters').onclick = () => {
      state.search = ''; state.date = ''; state.sort = 'created_at'; state.order = 'desc'; state.page = 1;
      load().catch(showError);
    };
    root.querySelector('#previous-page').onclick = () => { state.page -= 1; render(samples, samples.slice((state.page - 1) * PAGE_SIZE, state.page * PAGE_SIZE), totalPages); };
    root.querySelector('#next-page').onclick = () => { state.page += 1; render(samples, samples.slice((state.page - 1) * PAGE_SIZE, state.page * PAGE_SIZE), totalPages); };
    root.querySelectorAll('[data-select-sample]').forEach(input => input.onchange = () => {
      const id = Number(input.dataset.selectSample);
      input.checked ? state.selected.add(id) : state.selected.delete(id);
      render(samples, visible, totalPages);
    });
    root.querySelectorAll('[data-delete-sample]').forEach(button => button.onclick = async () => {
      const id = Number(button.dataset.deleteSample);
      if (!confirm('Delete this sample, its analysis, and stored images?')) return;
      button.disabled = true;
      try {
        await api.deleteSample(id);
        state.selected.delete(id);
        toast('Sample deleted');
        await load();
      } catch (error) { button.disabled = false; toast(error.message, true); }
    });
    root.querySelector('#delete-selected').onclick = async () => {
      if (!state.selected.size || !confirm(`Delete ${state.selected.size} selected sample(s), analyses, and images?`)) return;
      try {
        await Promise.all([...state.selected].map(id => api.deleteSample(id)));
        state.selected.clear();
        toast('Selected samples deleted');
        await load();
      } catch (error) { toast(error.message, true); }
    };
    root.querySelector('#compare-samples').onclick = () => compareSelected();
  }

  async function compareSelected() {
    const panel = root.querySelector('#comparison');
    panel.classList.remove('hide');
    panel.innerHTML = '<div class="loading"><i class="spinner"></i><span>Loading selected results…</span></div>';
    try {
      const results = await Promise.all([...state.selected].map(id => api.sample(id)));
      const comparable = results.filter(result => result.analysis);
      if (comparable.length < 2) throw new Error('Select at least two samples that have completed analyses.');
      const labels = comparable.map(result => result.sample.name || `Sample ${result.sample.id}`);
      const values = comparable.map(result => result.analysis.suspected_plastic);
      panel.innerHTML = `<h2>Selected sample comparison</h2>${barChart(labels, values, { label: 'Suspected particle count by selected sample' })}<div class="table-wrap" style="margin-top:1rem"><table class="table"><thead><tr><th>Sample</th><th>Suspected</th><th>Total</th><th>Fibers</th><th>Fragments</th><th>Concentration</th></tr></thead><tbody>${comparable.map(result => `<tr><td><a href="#/sample/${result.sample.id}">${escapeHtml(result.sample.name)}</a></td><td>${number(result.analysis.suspected_plastic)}</td><td>${number(result.analysis.total_particles)}</td><td>${number(result.analysis.fibers)}</td><td>${number(result.analysis.fragments)}</td><td>${result.analysis.concentration_per_l === null ? '—' : `${number(result.analysis.concentration_per_l, 1)}/L`}</td></tr>`).join('')}</tbody></table></div>`;
    } catch (error) { panel.innerHTML = `<h2>Selected sample comparison</h2><p class="warning">${escapeHtml(error.message)}</p>`; }
  }

  function showError(error) {
    root.innerHTML = `<article class="card empty"><h2>Could not load sample history</h2><p>${escapeHtml(error.message)}</p><button type="button" onclick="location.reload()">Try again</button></article>`;
  }

  await load();
}

function table(samples, selected) {
  if (!samples.length) return '<p class="empty">No samples match these filters.</p>';
  return `<div class="table-wrap"><table class="table"><thead><tr><th></th><th>Preview</th><th>Sample</th><th>Date</th><th>Suspected</th><th>Total</th><th>Concentration</th><th></th></tr></thead><tbody>${samples.map(sample => `<tr><td><input type="checkbox" aria-label="Select ${escapeHtml(sample.name)}" data-select-sample="${sample.id}" ${selected.has(sample.id) ? 'checked' : ''}></td><td>${sample.analysis_id ? `<img class="thumb" src="${api.imageUrl(sample.analysis_id, 'annotated')}" alt="Annotated screening preview">` : '—'}</td><td><a href="#/sample/${sample.id}">${escapeHtml(sample.name)}</a><br><small class="muted">${escapeHtml(sample.location || '')}</small></td><td>${date(sample.created_at)}</td><td>${number(sample.suspected_plastic)}</td><td>${number(sample.total_particles)}</td><td>${sample.concentration_per_l === null ? '—' : `${number(sample.concentration_per_l, 1)}/L`}</td><td><button class="danger" type="button" data-delete-sample="${sample.id}">Delete</button></td></tr>`).join('')}</tbody></table></div>`;
}
