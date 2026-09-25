import { api } from '../api.js';
import { deviceKey, disclaimer, escapeHtml, navigate, number, setDeviceKey, toast } from '../app.js';

export async function renderDevice(root) {
  const settingsResponse = await api.settings();
  const settings = settingsResponse.settings;
  let previewTimer;

  root.innerHTML = `<section class="page-head"><div><h1>ESP32-CAM control</h1><p class="muted">Use only on your trusted local network. The dashboard must not be exposed to the public internet.</p></div><button id="open-capture" type="button">New camera analysis</button></section>
    <section class="grid two-col"><article class="card"><h2>Connection and live preview</h2><div class="form-grid"><div class="field"><label for="device-host">ESP32 host or IP</label><input id="device-host" value="${escapeHtml(settings.esp32_ip || '')}" placeholder="192.168.1.50"></div><div class="field"><label for="device-key">Device API key</label><input id="device-key" type="password" value="${escapeHtml(deviceKey())}" autocomplete="off" placeholder="Stored only in this browser"></div></div><div class="form-actions" style="margin-top:.8rem"><button id="save-device" type="button">Save host</button><button id="test-device" class="secondary" type="button">Test connection</button></div><p id="device-status" class="muted">Connection not tested.</p><div class="image-viewer" style="margin-top:1rem"><img id="preview-image" alt="Live ESP32-CAM preview" style="max-width:100%;max-height:420px"><p id="preview-empty" class="muted">Enter a camera host to refresh the live preview.</p></div></article>
      <article class="card"><h2>Chamber LED</h2><div class="field"><label for="led-level">Brightness <output id="led-output">180</output>/255</label><input id="led-level" type="range" min="0" max="255" value="180"></div><div class="form-actions" style="margin-top:1rem"><button id="led-on" type="button">Turn LED on</button><button id="led-off" class="secondary" type="button">Turn LED off</button></div><h2 style="margin-top:1.4rem">Device information</h2><dl id="device-info" class="muted"><dt>Status</dt><dd>Not available</dd></dl></article></section>
    <section class="grid two-col" style="margin-top:1rem"><article class="card"><h2>Camera settings</h2><form id="camera-config" class="form-grid"><div class="field"><label for="frame-size">Frame size</label><select id="frame-size"><option value="VGA">640×480 (VGA)</option><option value="SVGA">800×600 (SVGA)</option><option value="XGA">1024×768 (XGA)</option><option value="SXGA">1280×1024 (SXGA)</option><option value="UXGA">1600×1200 (UXGA)</option></select></div><div class="field"><label for="jpeg-quality">JPEG quality (lower is sharper)</label><input id="jpeg-quality" type="number" min="4" max="63" value="${number(settings.camera_quality, 0)}"></div><div class="field full"><label><input id="lock-exposure" type="checkbox"> Request exposure lock</label><p class="muted">Support depends on the camera firmware version.</p></div><div class="form-actions"><button type="submit">Apply camera settings</button></div></form></article>
      <article class="card"><h2>Firmware connection values</h2><p class="muted">Copy the server address into <span class="code">SERVER_URL</span> and configure the same device API key in the firmware’s <span class="code">secrets.h</span>.</p><div class="field"><label for="server-url">Server URL</label><input id="server-url" class="code" readonly value="${escapeHtml(location.origin)}"></div><div class="form-actions" style="margin-top:.8rem"><button id="copy-server-url" class="secondary" type="button">Copy server URL</button></div><p class="warning">The actual accepted API key is configured in the backend <span class="code">.env</span>. Do not share it or expose this local dashboard publicly.</p></article></section>${disclaimer()}`;

  const hostInput = root.querySelector('#device-host');
  const keyInput = root.querySelector('#device-key');
  const status = root.querySelector('#device-status');
  const preview = root.querySelector('#preview-image');
  const previewEmpty = root.querySelector('#preview-empty');
  root.querySelector('#frame-size').value = settings.camera_framesize || 'UXGA';

  function currentHost() { return hostInput.value.trim(); }
  function requireKey() {
    const key = keyInput.value.trim();
    if (!key) throw new Error('Enter the device API key first.');
    return key;
  }
  function updatePreview() {
    if (!root.contains(preview)) {
      clearTimeout(previewTimer);
      return;
    }
    const host = currentHost();
    if (host) {
      preview.hidden = false;
      previewEmpty.hidden = true;
      preview.src = `/api/device/stream-frame?esp32_ip=${encodeURIComponent(host)}&_=${Date.now()}`;
    } else {
      preview.hidden = true;
      previewEmpty.hidden = false;
    }
    previewTimer = setTimeout(updatePreview, 700);
  }
  function showStatus(result) {
    status.textContent = result.online ? `Online at ${result.host || currentHost()}` : `Offline: ${result.detail || 'No response'}`;
    status.className = result.online ? 'status-online' : 'status-offline';
    root.querySelector('#device-info').innerHTML = result.online ? `<dt>Network</dt><dd>${escapeHtml(result.host || currentHost())}</dd><dt>RSSI</dt><dd>${number(result.rssi, 0)} dBm</dd><dt>Free heap</dt><dd>${number(result.heap, 0)} bytes</dd><dt>Resolution</dt><dd>${escapeHtml(result.resolution || '—')}</dd><dt>Uptime</dt><dd>${number(result.uptime_ms ? result.uptime_ms / 1000 : null, 0)} seconds</dd>` : '<dt>Status</dt><dd>Camera is offline or unavailable.</dd>';
  }

  root.querySelector('#open-capture').onclick = () => navigate('/new');
  root.querySelector('#save-device').onclick = async () => {
    const host = currentHost();
    try {
      await api.updateSettings({ esp32_ip: host });
      setDeviceKey(keyInput.value.trim());
      toast('Camera host saved. API key remains only in this browser.');
      clearTimeout(previewTimer);
      updatePreview();
    } catch (error) { toast(error.message, true); }
  };
  root.querySelector('#test-device').onclick = async buttonEvent => {
    const button = buttonEvent.currentTarget;
    button.disabled = true; status.textContent = 'Testing connection…';
    try { showStatus(await api.deviceStatus(currentHost())); }
    catch (error) { showStatus({ online: false, detail: error.message }); }
    finally { button.disabled = false; }
  };
  root.querySelector('#led-level').oninput = event => { root.querySelector('#led-output').textContent = event.target.value; };
  root.querySelector('#led-on').onclick = async () => {
    try {
      await api.deviceLed({ state: 'on', level: Number(root.querySelector('#led-level').value) }, requireKey());
      toast('Chamber LED turned on');
    } catch (error) { toast(error.message, true); }
  };
  root.querySelector('#led-off').onclick = async () => {
    try {
      await api.deviceLed({ state: 'off', level: 0 }, requireKey());
      toast('Chamber LED turned off');
    } catch (error) { toast(error.message, true); }
  };
  root.querySelector('#camera-config').onsubmit = async event => {
    event.preventDefault();
    const button = event.currentTarget.querySelector('button');
    button.disabled = true;
    try {
      const values = { framesize: root.querySelector('#frame-size').value, quality: Number(root.querySelector('#jpeg-quality').value), lock_exposure: root.querySelector('#lock-exposure').checked };
      await api.deviceConfig(values, requireKey());
      await api.updateSettings({ camera_framesize: values.framesize, camera_quality: values.quality });
      toast('Camera settings applied');
    } catch (error) { toast(error.message, true); }
    finally { button.disabled = false; }
  };
  root.querySelector('#copy-server-url').onclick = async () => {
    try { await navigator.clipboard.writeText(root.querySelector('#server-url').value); toast('Server URL copied'); }
    catch { toast('Copy failed; select the URL and copy it manually.', true); }
  };
  updatePreview();
}
