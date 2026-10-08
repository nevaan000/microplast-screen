import { renderDashboard } from './pages/dashboard.js';
import { renderNewAnalysis } from './pages/new-analysis.js';
import { renderSample } from './pages/sample.js';
import { renderHistory } from './pages/history.js';
import { renderCalibration } from './pages/calibration.js';
import { renderDevice } from './pages/device.js';
import { renderMl } from './pages/ml.js';
import { renderSettings } from './pages/settings.js';
import { renderAbout } from './pages/about.js';
import { api, AuthRequired } from './api.js';

const navigation = [
  ['/', 'Dashboard'], ['/new', 'New analysis'], ['/history', 'History'], ['/calibration', 'Calibration'],
  ['/device', 'Device'], ['/ml', 'ML lab'], ['/settings', 'Settings'], ['/about', 'Method & limitations'],
];

export const DISCLAIMER = 'This is a low-cost optical screening result. It estimates particles that visually resemble microplastics and is not a laboratory-grade chemical identification. Confirm with FTIR/Raman spectroscopy.';

export const escapeHtml = value => String(value ?? '').replace(/[&<>'"]/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' })[char]);
export const number = (value, digits = 0) => value === null || value === undefined || Number.isNaN(Number(value)) ? '—' : Number(value).toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: digits });
export const date = value => value ? new Date(value).toLocaleString() : '—';
export const disclaimer = () => `<p class="disclaimer">${DISCLAIMER}</p>`;
export const loading = () => '<div class="loading"><i class="spinner"></i><span>Loading visual screening data…</span></div>';

export function toast(message, error = false) {
  const element = document.createElement('div');
  element.className = `toast${error ? ' error' : ''}`;
  element.textContent = message;
  document.querySelector('#toast-region').append(element);
  setTimeout(() => element.remove(), 4300);
}

export function deviceKey() { return localStorage.getItem('microplast-device-key') || ''; }
export function setDeviceKey(value) { localStorage.setItem('microplast-device-key', value); }
export function navigate(path) { location.hash = `#${path}`; }

let authState = { auth_enabled: false, authenticated: true, user: null };
const locked = () => authState.auth_enabled && !authState.authenticated;

function shell() {
  const foot = authState.auth_enabled
    ? 'Single-user dashboard behind a login. Keep the password private and serve this host over HTTPS only.'
    : 'Local/LAN operation only. Do not expose this dashboard to the public internet.';
  document.querySelector('#app').innerHTML = `<div class="shell"><aside class="sidebar"><div class="brand">MicroPlast Screen<small>Optical visual screening</small></div><nav class="nav">${navigation.map(([path, label]) => `<a href="#${path}" data-path="${path}">${label}</a>`).join('')}</nav><div class="sidebar-foot">${foot}</div></aside><section class="content"><header class="topbar"><div><h1 id="page-title">MicroPlast Screen</h1><p id="page-subtitle">Suspected microplastic visual screening</p></div><div class="top-actions">${authState.auth_enabled ? `<span class="chip">${escapeHtml(authState.user || 'signed in')}</span><button id="sign-out" class="secondary" type="button">Sign out</button>` : ''}<button id="theme-toggle" class="secondary" type="button" aria-label="Toggle theme">Theme</button><a class="chip" href="/docs" target="_blank" rel="noopener">API docs</a></div></header><main id="page-content"></main></section></div>`;
  document.querySelector('#theme-toggle').onclick = () => {
    document.body.classList.toggle('dark');
    localStorage.setItem('microplast-theme', document.body.classList.contains('dark') ? 'dark' : 'light');
  };
  const signOut = document.querySelector('#sign-out');
  if (signOut) {
    signOut.onclick = async () => {
      await api.logout().catch(() => {});
      authState = await api.me().catch(() => ({ auth_enabled: true, authenticated: false, user: null }));
      renderLogin();
    };
  }
}

function renderLogin() {
  document.querySelector('#app').innerHTML = `<div class="login-wrap"><form class="card login-card" id="login-form"><div class="brand">MicroPlast Screen<small>Optical visual screening</small></div><p class="muted">Sign in to view and manage your visual screening results.</p><div class="field"><label for="login-user">Username</label><input id="login-user" name="username" autocomplete="username" maxlength="80" required></div><div class="field"><label for="login-pass">Password</label><input id="login-pass" name="password" type="password" autocomplete="current-password" maxlength="200" required></div><p id="login-error" class="muted login-error" hidden></p><button type="submit">Sign in</button></form></div>`;
  document.querySelector('#login-form').onsubmit = async event => {
    event.preventDefault();
    const error = document.querySelector('#login-error');
    const button = event.target.querySelector('button[type=submit]');
    error.hidden = true;
    button.disabled = true;
    try {
      await api.login(document.querySelector('#login-user').value.trim(), document.querySelector('#login-pass').value);
      authState = await api.me();
      document.querySelector('#app').innerHTML = '';
      shell();
      route();
    } catch (loginError) {
      error.textContent = loginError.message;
      error.hidden = false;
      button.disabled = false;
    }
  };
}

function parseRoute() {
  const path = location.hash.slice(1) || '/';
  const sampleMatch = path.match(/^\/sample\/(\d+)$/);
  return sampleMatch ? { page: 'sample', id: sampleMatch[1], path } : { page: path, path };
}

const pages = {
  '/': ['Dashboard', 'Overview of local visual screening results', renderDashboard],
  '/new': ['New analysis', 'Upload images, capture from a device, or generate a synthetic demo', renderNewAnalysis],
  '/history': ['History', 'Browse, compare, and manage analyzed samples', renderHistory],
  '/calibration': ['Calibration', 'Set the pixel-to-millimetre scale for reliable size measurements', renderCalibration],
  '/device': ['ESP32-CAM device', 'Connect, preview, and control your local camera', renderDevice],
  '/ml': ['ML lab', 'Review and retrain the visual shape classifier', renderMl],
  '/settings': ['Settings', 'Configure optical screening and device parameters', renderSettings],
  '/about': ['Method & limitations', 'What this visual screening system can and cannot determine', renderAbout],
  sample: ['Sample results', 'Visual screening analysis details', renderSample],
};

async function route() {
  if (locked()) { renderLogin(); return; }
  const route = parseRoute();
  if (!document.querySelector('.shell')) shell();
  if (route.page === '/login') { navigate('/'); return; }
  const [title, subtitle, renderer] = pages[route.page] || pages['/'];
  document.querySelector('#page-title').textContent = title;
  document.querySelector('#page-subtitle').textContent = subtitle;
  document.querySelectorAll('.nav a').forEach(link => link.classList.toggle('active', link.dataset.path === route.path || (route.page === 'sample' && link.dataset.path === '/history')));
  const root = document.querySelector('#page-content');
  root.innerHTML = loading();
  try {
    await renderer(root, route);
  } catch (error) {
    if (error instanceof AuthRequired) {
      authState = { ...authState, authenticated: false };
      renderLogin();
      return;
    }
    root.innerHTML = `<div class="card empty"><h2>Could not load this page</h2><p>${escapeHtml(error.message)}</p><button type="button" onclick="location.reload()">Try again</button></div>`;
  }
}

async function initialize() {
  if (localStorage.getItem('microplast-theme') === 'dark') document.body.classList.add('dark');
  authState = await api.me().catch(() => ({ auth_enabled: false, authenticated: true, user: null }));
  addEventListener('hashchange', route);
  route();
}

initialize();
