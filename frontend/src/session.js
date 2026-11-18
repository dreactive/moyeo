import {getDataMode,requestJson} from './api.js';
import {showError} from './ui.js';

export function pageUrl(path) {
  const base = 'http://workspace.local';
  let url = new URL('/rooms',base);
  try {
    const value = String(path ?? '');
    const decoded = decodeURIComponent(value);
    const candidate = new URL(value,base);
    const pathname = decodeURIComponent(candidate.pathname);
    if (value.startsWith('/') && candidate.origin === base && !/[\\\u0000-\u001f\u007f]/.test(decoded)
      && !pathname.startsWith('//') && !/[\\\u0000-\u001f\u007f]/.test(pathname)) url = candidate;
  } catch { /* Invalid paths use the local room selection page. */ }
  if (getDataMode() === 'fixture') url.searchParams.set('mode', 'fixture');
  return url.pathname + url.search + url.hash;
}

export function navigate(path) {
  location.assign(pageUrl(path));
}

export async function requireSession() {
  try {
    return await requestJson('/api/auth/me');
  } catch (error) {
    if (error.status !== 401) throw error;
    navigate('/login.html');
    return null;
  }
}

function roomKey() {
  return getDataMode() === 'fixture' ? 'trip-fixture-room' : 'trip-room';
}

export function saveRoomId(id) {
  sessionStorage.setItem(roomKey(), id);
}

export function readRoomId() {
  return sessionStorage.getItem(roomKey());
}

export function clearRoomId() {
  sessionStorage.removeItem(roomKey());
}

export async function signOut() {
  await requestJson('/api/auth/logout', {method:'POST'});
  clearRoomId();
  navigate('/login.html');
}

function reloadRestoredPage(event) {
  if (event.persisted) location.reload();
}

export function preparePage() {
  globalThis.addEventListener?.('pageshow', reloadRestoredPage);
  document.getElementById('mode').textContent = getDataMode() === 'fixture'
    ? '개발용 fixture · 실제 계정/여행 데이터 아님'
    : 'LIVE · Backend 연결';
  for (const link of document.querySelectorAll('[data-app-link]')) {
    link.href = pageUrl(link.dataset.appLink || link.getAttribute('href'));
  }
}

export function bindEntryForm(form, task, onError = showError, controls) {
  const button = form.querySelector('button[type=submit]');
  const group = controls ?? [button];
  form.onsubmit = async event => {
    event.preventDefault();
    if (button.disabled) return;
    const available = group.filter(control => !control.disabled);
    available.forEach(control => control.disabled = true);
    showError(null);
    try {
      await task(form);
    } catch (error) {
      available.forEach(control => control.disabled = false);
      onError(error);
    }
  };
}
