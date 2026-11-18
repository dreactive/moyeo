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

test('sign-out clears room selection after the server accepts it', async () => {
  const actions = [];
  globalThis.location = {search:'',assign: url => actions.push(url)};
  globalThis.sessionStorage = {removeItem: key => actions.push(key)};
  globalThis.fetch = async (path, options) => {
    actions.push([path, options.method]);
    return Response.json({ok:true});
  };
  await session.signOut();
  assert.deepEqual(actions, [['/api/auth/logout','POST'],'trip-room','/login.html']);
});
