import {getDataMode,requestJson} from './api.js';
import {showError} from './ui.js';

export function pageUrl(path) {
  const url = new URL(path, 'http://workspace.local');
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

export function preparePage() {
  document.getElementById('mode').textContent = getDataMode() === 'fixture'
    ? '개발용 fixture · 실제 계정/여행 데이터 아님'
    : 'LIVE · Backend 연결';
  for (const link of document.querySelectorAll('[data-app-link]')) {
    link.href = pageUrl(link.dataset.appLink || link.getAttribute('href'));
  }
}

export function bindEntryForm(form, task, onError = showError) {
  const button = form.querySelector('button[type=submit]');
  form.onsubmit = async event => {
    event.preventDefault();
    if (button.disabled) return;
    button.disabled = true;
    showError(null);
    try {
      await task(form);
    } catch (error) {
      button.disabled = false;
      onError(error);
    }
  };
}
