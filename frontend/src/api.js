import {requestFixture} from './fixture-api.js';
export const getDataMode = () => new URLSearchParams(globalThis.location?.search).get('mode') === 'fixture' ? 'fixture' : 'live';
export async function requestJson(path, options = {}) {
  if (getDataMode() === 'fixture') return requestFixture(path, options);
  const response = await fetch(path, {credentials:'same-origin', ...options,
    headers:{'Content-Type':'application/json', ...options.headers},
    body:options.body === undefined ? undefined : JSON.stringify(options.body)});
  if (!response.ok) throw new Error('요청 실패 (' + response.status + ')');
  return response.json();
}
