import { api } from '../api.js';
import { disclaimer, escapeHtml, toast } from '../app.js';

const GROUPS = [
  {
    title: 'Preprocessing and segmentation',
    fields: [
      ['illumination_correction', 'Illumination correction', 'boolean'],
      ['background_mode', 'Filter background', 'select', [['light_filter', 'Light filter (darker particles)'], ['dark_filter', 'Dark filter (brighter particles)']]],
      ['threshold_method', 'Intensity threshold', 'select', [['otsu', 'Otsu'], ['adaptive', 'Adaptive'], ['fixed', 'Fixed']]],
      ['fixed_threshold', 'Fixed threshold', 'number', { min: 0, max: 255, step: 1 }],
      ['adaptive_block_size', 'Adaptive block size', 'number', { min: 3, step: 2 }],
      ['adaptive_c', 'Adaptive C offset', 'number', { step: 1 }],
      ['sat_threshold', 'Saturation threshold', 'number', { min: 0, max: 255, step: 1 }],
      ['opening_kernel', 'Opening kernel size', 'number', { min: 1, step: 2 }],
      ['opening_iterations', 'Opening iterations', 'number', { min: 0, max: 10, step: 1 }],
      ['closing_kernel', 'Closing kernel size', 'number', { min: 1, step: 2 }],
      ['closing_iterations', 'Closing iterations', 'number', { min: 0, max: 10, step: 1 }],
    ],
  },
  {
    title: 'Particle and ROI filtering',
    fields: [
      ['min_area_px', 'Minimum particle area (px²)', 'number', { min: 1, step: 1 }],
      ['max_area_percent', 'Maximum area (% image)', 'number', { min: 0.01, max: 100, step: 0.01 }],
      ['border_margin_percent', 'Ignored border margin (%)', 'number', { min: 0, max: 49, step: 0.1 }],
      ['roi_mode', 'Region of interest', 'select', [['none', 'Use full image'], ['circle', 'Circular ROI']]],
      ['roi_center_x', 'ROI centre X (0–1)', 'number', { min: 0, max: 1, step: 0.01 }],
      ['roi_center_y', 'ROI centre Y (0–1)', 'number', { min: 0, max: 1, step: 0.01 }],
      ['roi_radius_percent', 'ROI radius (% width)', 'number', { min: 1, max: 50, step: 0.1 }],
    ],
  },
  {
    title: 'Visual classification and reporting',
    fields: [
      ['plastic_threshold', 'Suspected-plastic threshold', 'number', { min: 0, max: 1, step: 0.01 }],
      ['classifier_mode', 'Classifier mode', 'select', [['rules', 'Rules'], ['ml', 'ML'], ['hybrid', 'Hybrid']]],
      ['fiber_aspect_ratio', 'Fiber aspect-ratio threshold', 'number', { min: 1, step: 0.1 }],
      ['fiber_width_px', 'Maximum fiber width (px)', 'number', { min: 1, step: 0.1 }],
      ['fiber_width_mm', 'Maximum fiber width (mm)', 'number', { min: 0.001, step: 0.001 }],
      ['min_reliable_px', 'Minimum reliable size (px)', 'number', { min: 1, step: 1 }],
      ['size_bins_mm', 'Size-bin upper edges (mm)', 'list'],
    ],
  },
  {
    title: 'Device defaults',
    fields: [
      ['esp32_ip', 'ESP32 host or IP', 'text'],
      ['camera_framesize', 'Camera frame size', 'select', [['VGA', 'VGA'], ['SVGA', 'SVGA'], ['XGA', 'XGA'], ['SXGA', 'SXGA'], ['UXGA', 'UXGA']]],
      ['camera_quality', 'Camera JPEG quality', 'number', { min: 4, max: 63, step: 1 }],
    ],
  },
];

export async function renderSettings(root) {
  const response = await api.settings();
  const settings = response.settings;
  root.innerHTML = `<section class="page-head"><div><h1>Screening settings</h1><p class="muted">These values apply to new and reanalyzed visual screening results.</p></div><button id="reset-settings" class="secondary" type="button">Restore defaults</button></section>
    <form id="settings-form">${GROUPS.map(group => `<article class="card settings-group"><h2>${group.title}</h2><div class="form-grid">${group.fields.map(field => control(field, settings)).join('')}</div></article>`).join('')}<div class="form-actions"><button type="submit">Save settings</button></div></form>
    <article class="card" style="margin-top:1rem"><h2>Device API key</h2><p class="muted">The accepted key is set with <span class="code">DEVICE_API_KEY</span> in the backend <span class="code">.env</span>. Enter it only in the Device page, where it remains in this browser’s local storage and is never displayed here.</p></article>${disclaimer()}`;

  root.querySelector('#settings-form').onsubmit = async event => {
    event.preventDefault();
    const values = {};
    root.querySelectorAll('[data-setting]').forEach(input => {
      const key = input.dataset.setting;
      const type = input.dataset.type;
      if (type === 'boolean') values[key] = input.checked;
      else if (type === 'number') values[key] = Number(input.value);
      else if (type === 'list') values[key] = input.value.split(',').map(value => Number(value.trim())).filter(value => Number.isFinite(value) && value > 0);
      else values[key] = input.value.trim();
    });
    if (!values.size_bins_mm.length) {
      toast('Enter at least one positive size-bin upper edge.', true);
      return;
    }
    const button = event.currentTarget.querySelector('button');
    button.disabled = true;
    try {
      await api.updateSettings(values);
      toast('Screening settings saved');
    } catch (error) { toast(error.message, true); }
    finally { button.disabled = false; }
  };
  root.querySelector('#reset-settings').onclick = async () => {
    if (!confirm('Restore all screening and device defaults?')) return;
    try {
      await api.resetSettings();
      toast('Default settings restored');
      await renderSettings(root);
    } catch (error) { toast(error.message, true); }
  };
}

function control([key, label, type, options], settings) {
  const value = settings[key];
  if (type === 'boolean') return `<div class="field"><label><input type="checkbox" data-setting="${key}" data-type="boolean" ${value ? 'checked' : ''}> ${label}</label></div>`;
  if (type === 'select') return `<div class="field"><label for="setting-${key}">${label}</label><select id="setting-${key}" data-setting="${key}" data-type="text">${options.map(([option, name]) => `<option value="${escapeHtml(option)}" ${value === option ? 'selected' : ''}>${escapeHtml(name)}</option>`).join('')}</select></div>`;
  const attributes = options ? Object.entries(options).map(([name, entry]) => `${name}="${entry}"`).join(' ') : '';
  const displayValue = type === 'list' ? (Array.isArray(value) ? value.join(', ') : '') : value ?? '';
  return `<div class="field"><label for="setting-${key}">${label}</label><input id="setting-${key}" data-setting="${key}" data-type="${type === 'number' ? 'number' : type}" type="${type === 'number' ? 'number' : 'text'}" value="${escapeHtml(displayValue)}" ${attributes}></div>`;
}
