import {getDataMode,requestJson} from './api.js';

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
