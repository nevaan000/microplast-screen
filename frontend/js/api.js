const base = '/api';

function requestError(body) {
  if (typeof body !== 'object' || body === null) return body || 'Request failed';
  if (typeof body.detail === 'string') return body.detail;
  if (Array.isArray(body.detail)) return body.detail.map(item => `${item.loc?.at(-1) || 'Request'}: ${item.msg || 'Invalid value'}`).join('; ');
  return 'Request failed';
}

async function request(path, options = {}) {
  const response = await fetch(`${base}${path}`, options);
  const type = response.headers.get('content-type') || '';
  const body = type.includes('application/json') ? await response.json() : await response.text();
  if (!response.ok) throw new Error(requestError(body));
  return body;
}

const json = (method, path, payload, headers = {}) => request(path, {
  method, headers: { 'Content-Type': 'application/json', ...headers }, body: payload === undefined ? undefined : JSON.stringify(payload),
});

export const api = {
  request,
  health: () => request('/health'),
  overview: () => request('/stats/overview'),
  samples: (params = {}) => request(`/samples?${new URLSearchParams(params)}`),
  sample: id => request(`/samples/${id}`),
  createSample: values => json('POST', '/samples', values),
  updateSample: (id, values) => json('PATCH', `/samples/${id}`, values),
  deleteSample: id => request(`/samples/${id}`, { method: 'DELETE' }),
  uploadAnalysis: data => request('/analyze', { method: 'POST', body: data }),
  reanalyze: id => request(`/samples/${id}/reanalyze`, { method: 'POST' }),
  demo: values => json('POST', '/demo/generate', values),
  settings: () => request('/settings'),
  updateSettings: values => json('PUT', '/settings', { values }),
  resetSettings: () => request('/settings/reset', { method: 'POST' }),
  calibrations: () => request('/calibration'),
  createCalibration: values => json('POST', '/calibration', values),
  activateCalibration: calibration_id => json('POST', '/calibration/active', { calibration_id }),
  deviceStatus: host => request(`/device/status${host ? `?esp32_ip=${encodeURIComponent(host)}` : ''}`),
  deviceLed: (values, key) => json('POST', '/device/led', values, deviceHeaders(key)),
  deviceCapture: (values, key) => json('POST', '/device/capture', values, deviceHeaders(key)),
  deviceConfig: (values, key) => json('POST', '/device/config', values, deviceHeaders(key)),
  modelStatus: () => request('/ml/status'),
  trainModel: values => json('POST', '/ml/train', values),
  correctParticle: (id, user_verified_class) => json('PATCH', `/particles/${id}`, { user_verified_class }),
  imageUrl: (analysisId, type) => `${base}/images/${analysisId}/${type}`,
  exportUrl: (sampleId, type) => `${base}/export/${sampleId}.${type}`,
};

function deviceHeaders(key) {
  return key ? { 'X-API-Key': key } : {};
}
