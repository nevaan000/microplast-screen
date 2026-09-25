import { api } from '../api.js';
import { deviceKey, navigate, toast } from '../app.js';

export async function renderNewAnalysis(root) {
  let mode = 'upload';
  root.innerHTML = `<form id="analysis-form"><div class="card"><div class="tabs"><button type="button" class="active" data-mode="upload">Upload images</button><button type="button" data-mode="capture">Capture from ESP32-CAM</button><button type="button" data-mode="demo">Demo (synthetic)</button></div><div id="mode-panel"></div><h2>Sample details</h2><div class="form-grid"><div class="field"><label for="sample-name">Sample name</label><input id="sample-name" name="name" maxlength="150" placeholder="Optional descriptive name"></div><div class="field"><label for="location">Location</label><input id="location" name="location" maxlength="250" placeholder="Collection location"></div><div class="field"><label for="volume">Water volume (mL)</label><input id="volume" name="volume_ml" type="number" min="0.001" step="any" placeholder="e.g. 500"></div><div class="field"><label for="pore">Filter pore size (µm)</label><input id="pore" name="filter_pore_um" type="number" min="0.001" step="any" placeholder="e.g. 20"></div><div class="field full"><label for="notes">Notes</label><textarea id="notes" name="notes" maxlength="5000" placeholder="Sample or imaging notes"></textarea></div></div><div class="form-actions" style="margin-top:1rem"><button id="submit-analysis" type="submit">Analyse images</button><span id="analysis-status" class="muted"></span></div><div class="progress" aria-hidden="true" style="margin-top:.7rem"><i id="analysis-progress"></i></div></div></form>`;
  const panel = root.querySelector('#mode-panel');
  const submit = root.querySelector('#submit-analysis');
  const setMode = next => {
    mode = next;
    root.querySelectorAll('[data-mode]').forEach(button => button.classList.toggle('active', button.dataset.mode === mode));
    submit.textContent = mode === 'upload' ? 'Analyse images' : mode === 'capture' ? 'Capture & analyse' : 'Generate & analyse';
    panel.innerHTML = mode === 'upload' ? uploadPanel() : mode === 'capture' ? capturePanel() : demoPanel();
    if (mode === 'upload') attachUploadPreview(panel);
  };
  root.querySelectorAll('[data-mode]').forEach(button => button.onclick = () => setMode(button.dataset.mode));
  setMode(mode);
  root.querySelector('#analysis-form').onsubmit = async event => {
    event.preventDefault();
    const status = root.querySelector('#analysis-status');
    const progress = root.querySelector('#analysis-progress');
    const details = formValues(event.currentTarget);
    submit.disabled = true; progress.style.width = '35%'; status.textContent = 'Preparing images…';
    try {
      let result;
      if (mode === 'upload') {
        const files = [...panel.querySelector('#image-files').files];
        if (!files.length) throw new Error('Select at least one JPEG or PNG image');
        const data = new FormData();
        files.forEach(file => data.append('images', file));
        Object.entries(details).forEach(([key, value]) => { if (value !== undefined && value !== '') data.append(key, value); });
        status.textContent = 'Running optical screening…'; progress.style.width = '65%';
        result = await api.uploadAnalysis(data);
      } else if (mode === 'capture') {
        if (!deviceKey()) throw new Error('Enter the device API key on the Device page before capturing.');
        const sample = await api.createSample({ ...details, name: details.name || `ESP32 capture ${new Date().toLocaleString()}` });
        const frames = Number(panel.querySelector('#frame-count').value);
        const led = panel.querySelector('#led-on').checked;
        if (led) await api.deviceLed({ state: 'on', level: Number(panel.querySelector('#led-level').value) }, deviceKey());
        try { result = await api.deviceCapture({ sample_id: sample.id, frames }, deviceKey()); }
        finally { if (led) api.deviceLed({ state: 'off', level: 0 }, deviceKey()).catch(() => {}); }
      } else {
        result = await api.demo({ ...details, n_particles: Number(panel.querySelector('#particle-count').value), fibre_ratio: Number(panel.querySelector('#fibre-ratio').value), noise: Number(panel.querySelector('#noise').value), lighting_gradient: Number(panel.querySelector('#gradient').value) });
      }
      progress.style.width = '100%';
      toast(`Analysis complete: ${result.analysis.total_particles} particles screened`);
      navigate(`/sample/${result.sample.id}`);
    } catch (error) { status.textContent = error.message; toast(error.message, true); progress.style.width = '0'; submit.disabled = false; }
  };
}

function uploadPanel() { return `<section><h2>Upload filter images</h2><label class="drop-zone" for="image-files">Choose one or more JPEG/PNG frames. Multiple frames are median-stacked to reduce sensor noise.<input id="image-files" type="file" accept="image/jpeg,image/png" multiple class="hide"></label><div id="file-previews" class="previews"></div></section>`; }
function capturePanel() { return `<section class="form-grid"><div class="field"><label for="frame-count">Frames to capture</label><input id="frame-count" type="number" min="1" max="10" value="3"></div><div class="field"><label for="led-level">LED brightness</label><input id="led-level" type="range" min="0" max="255" value="180"></div><div class="field full"><label><input id="led-on" type="checkbox" checked> Turn on chamber LED for this capture</label><p class="muted">The configured ESP32-CAM must be online. See the Device page to test its live preview and configure credentials.</p></div></section>`; }
function demoPanel() { return `<section class="form-grid"><div class="field"><label for="particle-count">Particle count <output></output></label><input id="particle-count" type="range" min="10" max="250" value="80"></div><div class="field"><label for="fibre-ratio">Fibre ratio <output></output></label><input id="fibre-ratio" type="range" min="0" max="1" step=".05" value=".35"></div><div class="field"><label for="noise">Sensor noise <output></output></label><input id="noise" type="range" min="0" max="25" value="7"></div><div class="field"><label for="gradient">Lighting gradient <output></output></label><input id="gradient" type="range" min="0" max=".5" step=".01" value=".12"></div></section>`; }

function attachUploadPreview(panel) { panel.querySelector('#image-files').onchange = event => { panel.querySelector('#file-previews').innerHTML = [...event.target.files].map(file => `<img src="${URL.createObjectURL(file)}" alt="Selected ${file.name}">`).join(''); }; }
function formValues(form) { const formData = new FormData(form); const values = Object.fromEntries(formData.entries()); for (const key of ['name', 'location', 'notes']) values[key] = values[key].trim() || undefined; for (const key of ['volume_ml', 'filter_pore_um']) values[key] = values[key] ? Number(values[key]) : undefined; return values; }
