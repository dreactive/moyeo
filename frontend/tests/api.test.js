import test from 'node:test';
import assert from 'node:assert/strict';
import {getDataMode,requestJson} from '../src/api.js';
test('only explicit fixture selects local DTOs and live errors propagate', async () => {
  globalThis.location = {search:'?mode=fixture'};
  assert.equal(getDataMode(), 'fixture');
  await requestJson('/api/auth/login', {method:'POST'});
  assert.equal((await requestJson('/api/rooms/room-fixture')).room_id,'room-fixture');
  location.search = '?mode=other';
  globalThis.fetch = async () => new Response('offline', {status:503});
  await assert.rejects(requestJson('/api/auth/me'), /503/);
});

test('HTTP errors retain their status for callers', async () => {
  globalThis.location = {search:''};
  globalThis.fetch = async () => new Response('offline', {status:503});
  await assert.rejects(requestJson('/api/auth/me'), {status:503});
});
