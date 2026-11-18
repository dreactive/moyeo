import test from 'node:test';
import assert from 'node:assert/strict';
import * as session from '../src/session.js';

test('navigation carries only the selected fixture mode across pages', () => {
  globalThis.location = {search:'?mode=fixture&extra=value',assign: url => assert.equal(url,'/rooms.html?mode=fixture')};
  session.navigate('/rooms.html');
});

test('only a rejected session redirects the protected page', async () => {
  const visited = [];
  globalThis.location = {search:'',assign: url => visited.push(url)};
  globalThis.fetch = async () => new Response('', {status:503});
  await assert.rejects(session.requireSession(), {status:503});
  assert.deepEqual(visited, []);
  globalThis.fetch = async () => new Response('', {status:401});
  assert.equal(await session.requireSession(), null);
  assert.deepEqual(visited, ['/login.html']);
});

test('fixture navigation uses a separate selected room key', () => {
  globalThis.location = {search:'?mode=fixture'};
  globalThis.sessionStorage = {setItem: (key,id) => assert.deepEqual([key,id], ['trip-fixture-room','sample'])};
  session.saveRoomId('sample');
});
