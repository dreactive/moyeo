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

test('live requests retain cookies and translate JSON server errors', async () => {
  globalThis.location = {search:''};
  let sent;
  globalThis.fetch = async (path,options) => {
    sent = [path,options];
    return Response.json({detail:'Invalid credentials'},{status:401});
  };
  await assert.rejects(requestJson('/api/auth/login',{method:'POST',body:{email:'a@b.test'}}), error => error.status === 401 && /이메일 또는 비밀번호/.test(error.message));
  assert.equal(sent[1].credentials,'same-origin');
  assert.deepEqual(JSON.parse(sent[1].body),{email:'a@b.test'});
});

test('successful empty responses support room deletion', async () => {
  globalThis.location = {search:''};
  globalThis.fetch = async () => new Response(null,{status:204});
  assert.equal(await requestJson('/api/rooms/r1',{method:'DELETE'}),null);
});
