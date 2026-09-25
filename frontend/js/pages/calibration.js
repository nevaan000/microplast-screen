import { api } from '../api.js';
import { date, disclaimer, escapeHtml, number, toast } from '../app.js';

export async function renderCalibration(root) {
  const calibrationData = await api.calibrations();
  let points = [];
  let image = null;

  root.innerHTML = `<section class="page-head"><div><h1>Scale calibration</h1><p class="muted">Measure a known reference at the same camera distance and focus as filter images.</p></div><span class="chip ${calibrationData.active ? 'ok' : 'warn'}">${calibrationData.active ? `${number(calibrationData.active.mm_per_pixel, 5)} mm/px active` : 'Not calibrated'}</span></section>
    <section class="grid two-col"><article class="card"><h2>1. Measure a reference</h2><p class="muted">Upload a ruler or stage-micrometer image, then click two endpoints of a known distance.</p><div class="field"><label for="calibration-image">Reference image</label><input id="calibration-image" type="file" accept="image/jpeg,image/png"></div><canvas id="calibration-canvas" class="calibration-canvas" width="1" height="1" aria-label="Calibration image measurement area"></canvas><p id="measurement-status" class="muted">Choose an image, then click the first and second reference points.</p></article>
      <article class="card"><h2>2. Save scale</h2><form id="calibration-form" class="form-grid"><div class="field"><label for="pixel-distance">Measured pixel distance</label><input id="pixel-distance" type="number" step="any" readonly required></div><div class="field"><label for="real-mm">Known distance (mm)</label><input id="real-mm" type="number" min="0.0001" step="any" required placeholder="e.g. 10"></div><div class="field full"><label for="calibration-note">Reference note</label><textarea id="calibration-note" maxlength="500" placeholder="e.g. 10 mm ruler mark"></textarea></div><div class="form-actions"><button type="submit">Save active calibration</button></div></form><p class="notice">Keep the camera distance, focus, image resolution, and filter position fixed after calibration. Recalibrate whenever this imaging setup changes.</p></article></section>
    <article class="card" style="margin-top:1rem"><h2>Calibration history</h2>${historyTable(calibrationData.items)}</article>${disclaimer()}`;

  const canvas = root.querySelector('#calibration-canvas');
  const context = canvas.getContext('2d');
  const imageInput = root.querySelector('#calibration-image');
  const status = root.querySelector('#measurement-status');
  const pixelInput = root.querySelector('#pixel-distance');

  function draw() {
    if (!image) return;
    context.clearRect(0, 0, canvas.width, canvas.height);
    context.drawImage(image, 0, 0, canvas.width, canvas.height);
    if (points.length) {
      context.fillStyle = '#087f8c';
      context.strokeStyle = '#ffffff';
      context.lineWidth = Math.max(3, canvas.width / 400);
      points.forEach(point => {
        context.beginPath();
        context.arc(point.x, point.y, Math.max(6, canvas.width / 160), 0, Math.PI * 2);
        context.fill();
        context.stroke();
      });
    }
    if (points.length === 2) {
      context.strokeStyle = '#087f8c';
      context.lineWidth = Math.max(3, canvas.width / 300);
      context.beginPath();
      context.moveTo(points[0].x, points[0].y);
      context.lineTo(points[1].x, points[1].y);
      context.stroke();
    }
  }

  imageInput.onchange = event => {
    const [file] = event.target.files;
    if (!file) return;
    const url = URL.createObjectURL(file);
    const next = new Image();
    next.onload = () => {
      URL.revokeObjectURL(url);
      image = next;
      canvas.width = next.naturalWidth;
      canvas.height = next.naturalHeight;
      points = [];
      pixelInput.value = '';
      status.textContent = 'Click the first and second reference points.';
      draw();
    };
    next.src = url;
  };

  canvas.onclick = event => {
    if (!image) return;
    const bounds = canvas.getBoundingClientRect();
    const point = { x: (event.clientX - bounds.left) * canvas.width / bounds.width, y: (event.clientY - bounds.top) * canvas.height / bounds.height };
    points = points.length === 2 ? [point] : [...points, point];
    if (points.length === 2) {
      const distance = Math.hypot(points[1].x - points[0].x, points[1].y - points[0].y);
      pixelInput.value = distance.toFixed(3);
      status.textContent = `Measured ${number(distance, 3)} pixels. Enter the known millimetre distance and save.`;
    } else {
      pixelInput.value = '';
      status.textContent = 'Now click the second reference point.';
    }
    draw();
  };

  root.querySelector('#calibration-form').onsubmit = async event => {
    event.preventDefault();
    const payload = {
      pixel_distance: Number(pixelInput.value),
      real_mm: Number(root.querySelector('#real-mm').value),
      note: root.querySelector('#calibration-note').value.trim() || undefined,
    };
    if (!(payload.pixel_distance > 0) || !(payload.real_mm > 0)) {
      toast('Measure two points and enter a positive known distance.', true);
      return;
    }
    const button = event.currentTarget.querySelector('button');
    button.disabled = true;
    try {
      const created = await api.createCalibration(payload);
      toast(`${number(created.mm_per_pixel, 5)} mm/px is now active`);
      await renderCalibration(root);
    } catch (error) { toast(error.message, true); button.disabled = false; }
  };

  root.querySelectorAll('[data-activate-calibration]').forEach(button => button.onclick = async () => {
    button.disabled = true;
    try {
      const activated = await api.activateCalibration(Number(button.dataset.activateCalibration));
      toast(`${number(activated.mm_per_pixel, 5)} mm/px is now active`);
      await renderCalibration(root);
    } catch (error) { button.disabled = false; toast(error.message, true); }
  });
}

function historyTable(items) {
  if (!items.length) return '<p class="empty">No calibration has been saved. Results will remain in pixels until one is active.</p>';
  return `<div class="table-wrap"><table class="table"><thead><tr><th>Scale</th><th>Measured pixels</th><th>Known distance</th><th>Note</th><th>Date</th><th>Status</th></tr></thead><tbody>${items.map(item => `<tr><td>${number(item.mm_per_pixel, 5)} mm/px</td><td>${number(item.pixel_distance, 3)}</td><td>${number(item.real_mm, 3)} mm</td><td>${escapeHtml(item.note || '—')}</td><td>${date(item.created_at)}</td><td>${item.is_active ? '<span class="chip ok">Active</span>' : `<button class="secondary" type="button" data-activate-calibration="${item.id}">Set active</button>`}</td></tr>`).join('')}</tbody></table></div>`;
}
