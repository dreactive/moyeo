import {getDataMode} from './api.js';

export function pageUrl(path) {
  const url = new URL(path, 'http://workspace.local');
  if (getDataMode() === 'fixture') url.searchParams.set('mode', 'fixture');
  return url.pathname + url.search + url.hash;
}

export function navigate(path) {
  location.assign(pageUrl(path));
}
